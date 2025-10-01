import asyncio
from functools import lru_cache
from typing import Any, Literal, Mapping, Optional, Sequence

import httpx
from starlette import status
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    wait_exponential_jitter,
    wait_fixed,
    wait_incrementing,
    wait_random,
    wait_random_exponential,
)
from tenacity.wait import wait_base

from zee_api.extensions.extension import Extension
from zee_api.extensions.http.settings import HttpSettings, WaitSettings


class HttpxClient(Extension):
    """
    An HTTP client extension built on top of httpx.AsyncClient with support for retries, timeouts, and concurrency control.

    Attributes:
        _owns_client (bool): Indicates if the client instance is owned by this class.
        _client (httpx.AsyncClient): The underlying HTTP client instance.
        default_attempts (int): Default number of retry attempts for requests.
        _semaphore (Optional[asyncio.Semaphore]): Semaphore for controlling concurrency.
        _is_semaphore_enabled (bool): Indicates if the semaphore is enabled.
        default_wait (wait_base): Default wait policy for retries.
    """

    def __init__(
        self,
        settings: HttpSettings,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._owns_client = client is None

        timeout = httpx.Timeout(
            settings.timeout.timeout_op, connect=settings.timeout.timeout_connect
        )

        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            verify=settings.verify_ssl,
            limits=httpx.Limits(
                max_connections=settings.max_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
            follow_redirects=settings.follow_redirects
        )

        self.default_attempts = settings.default_retry_attempts

        self._semaphore = None
        self._is_semaphore_enabled = False
        if settings.semaphore_size > 0:
            self._is_semaphore_enabled = True
            self._semaphore = asyncio.Semaphore(settings.semaphore_size)

        self.default_wait = self._configure_wait(settings.wait)

    async def aclose(self) -> None:
        """
        Close the underlying HTTP client if it is owned by this instance.
        """
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        skip_retry_status: Optional[Sequence[int]] = (),
        raise_for_status: bool = True,
        retry_attempts: Optional[int] = None,
        wait_policy: Optional[wait_base] = None,
        timeout: Optional[httpx.Timeout | float] = None,
    ) -> httpx.Response:
        """
        Perform an HTTP request with retry and concurrency control.

        Args:
            method (Literal): HTTP method (e.g., "GET", "POST").
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            json (Optional[dict[str, Any]]): JSON payload for the request body.
            data (Optional[Mapping[str, Any]]): Form data for the request body.
            skip_retry_status (Optional[Sequence[int]]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            retry_attempts (Optional[int]): Number of retry attempts.
            wait_policy (Optional[wait_base]): Wait policy for retries.
            timeout (Optional[httpx.Timeout | float]): Timeout for the request.

        Returns:
            httpx.Response: The HTTP response.

        Raises:
            ValueError: If both `json` and `data` are provided.
            httpx.RequestError: For request-related errors.
            httpx.HTTPStatusError: For HTTP status-related errors.
        """
        headers = headers or {}

        if json is not None and data is not None:
            # TODO: add specific exception
            raise ValueError("Provide either 'json' or 'data', not both")

        if data is not None:
            normalized = {k.lower(): v for k, v in headers.items()}
            if "content-type" not in normalized:
                headers["Content-Type"] = "application/x-www-form-urlencoded"

        _skip = tuple(skip_retry_status or ())
        _retry_attempts = retry_attempts or self.default_attempts
        _wait = wait_policy or self.default_wait

        retry_decorator = retry(
            stop=stop_after_attempt(_retry_attempts),
            wait=_wait,
            retry=retry_if_exception(self._should_retry_factory(_skip)),
            reraise=True,
        )

        @retry_decorator
        async def _execute() -> httpx.Response:
            try:
                _resp = await self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    timeout=timeout or httpx.USE_CLIENT_DEFAULT,
                )

                if raise_for_status:
                    _resp.raise_for_status()

                return _resp
            except httpx.RequestError:
                # TODO: add log
                raise
            except httpx.HTTPStatusError:
                # TODO: add log
                raise

        if self._is_semaphore_enabled and self._semaphore:
            async with self._semaphore:
                resp = await _execute()
        else:
            resp = await _execute()

        return resp

    async def get(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        skip_retry_status: Sequence[int] = (),
        raise_for_status: bool = False,
        **kwargs,
    ) -> httpx.Response:
        """
        Perform a GET request.

        Args:
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            skip_retry_status (Sequence[int]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            **kwargs: Additional arguments for the request.

        Returns:
            httpx.Response: The HTTP response.
        """
        return await self.request(
            method="GET",
            url=url,
            headers=headers,
            params=params,
            skip_retry_status=skip_retry_status,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    async def post(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        skip_retry_status: Sequence[int] = (),
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Perform a POST request.

        Args:
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            json (Optional[dict[str, Any]]): JSON payload for the request body.
            data (Optional[Mapping[str, Any]]): Form data for the request body.
            skip_retry_status (Sequence[int]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            **kwargs: Additional arguments for the request.

        Returns:
            httpx.Response: The HTTP response.
        """
        return await self.request(
            method="POST",
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            skip_retry_status=skip_retry_status,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    async def put(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        skip_retry_status: Sequence[int] = (),
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Perform a PUT request.

        Args:
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            json (Optional[dict[str, Any]]): JSON payload for the request body.
            data (Optional[Mapping[str, Any]]): Form data for the request body.
            skip_retry_status (Sequence[int]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            **kwargs: Additional arguments for the request.

        Returns:
            httpx.Response: The HTTP response.
        """
        return await self.request(
            method="PUT",
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            skip_retry_status=skip_retry_status,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    async def patch(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        skip_retry_status: Sequence[int] = (),
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Perform a PATCH request.

        Args:
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            json (Optional[dict[str, Any]]): JSON payload for the request body.
            data (Optional[Mapping[str, Any]]): Form data for the request body.
            skip_retry_status (Sequence[int]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            **kwargs: Additional arguments for the request.

        Returns:
            httpx.Response: The HTTP response.
        """
        return await self.request(
            method="PATCH",
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            skip_retry_status=skip_retry_status,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    async def delete(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        skip_retry_status: Sequence[int] = (),
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Perform a DELETE request.

        Args:
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            json (Optional[dict[str, Any]]): JSON payload for the request body.
            data (Optional[Mapping[str, Any]]): Form data for the request body.
            skip_retry_status (Sequence[int]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            **kwargs: Additional arguments for the request.

        Returns:
            httpx.Response: The HTTP response.
        """
        return await self.request(
            method="DELETE",
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            skip_retry_status=skip_retry_status,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    async def head(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        skip_retry_status: Sequence[int] = (),
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Perform a HEAD request.

        Args:
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            json (Optional[dict[str, Any]]): JSON payload for the request body.
            data (Optional[Mapping[str, Any]]): Form data for the request body.
            skip_retry_status (Sequence[int]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            **kwargs: Additional arguments for the request.

        Returns:
            httpx.Response: The HTTP response.
        """
        return await self.request(
            method="HEAD",
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            skip_retry_status=skip_retry_status,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    async def options(
        self,
        url: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        skip_retry_status: Sequence[int] = (),
        raise_for_status: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Perform an OPTIONS request.

        Args:
            url (str): The URL to send the request to.
            headers (Optional[dict[str, str]]): HTTP headers to include in the request.
            params (Optional[dict[str, Any]]): Query parameters to include in the request.
            json (Optional[dict[str, Any]]): JSON payload for the request body.
            data (Optional[Mapping[str, Any]]): Form data for the request body.
            skip_retry_status (Sequence[int]): HTTP status codes to skip retries for.
            raise_for_status (bool): Whether to raise an exception for HTTP errors.
            **kwargs: Additional arguments for the request.

        Returns:
            httpx.Response: The HTTP response.
        """
        return await self.request(
            method="OPTIONS",
            url=url,
            headers=headers,
            params=params,
            json=json,
            data=data,
            skip_retry_status=skip_retry_status,
            raise_for_status=raise_for_status,
            **kwargs,
        )

    @staticmethod
    def _should_retry_factory(skip_retry_statuses: Sequence[int]):
        """
        Factory method to create a retry condition function.

        Args:
            skip_retry_statuses (Sequence[int]): HTTP status codes to skip retries for.

        Returns:
            Callable[[BaseException], bool]: A function that determines if a retry should be attempted.
        """
        transient_status = {
            status.HTTP_408_REQUEST_TIMEOUT,
            status.HTTP_409_CONFLICT,
            status.HTTP_425_TOO_EARLY,
            status.HTTP_429_TOO_MANY_REQUESTS,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            status.HTTP_502_BAD_GATEWAY,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_504_GATEWAY_TIMEOUT,
        }

        def _should_retry(exc: BaseException) -> bool:
            if isinstance(exc, httpx.RequestError):
                return True

            if isinstance(exc, httpx.HTTPStatusError):
                code = exc.response.status_code

                if code in skip_retry_statuses:
                    return False

                return code in transient_status

            return False

        return _should_retry

    @staticmethod
    def _configure_wait(wait_settings: WaitSettings) -> wait_base:
        """Configure the wait policy based on settings, the default is `exponential`"""
        if wait_settings.policy == "exponential_jitter":
            return wait_exponential_jitter(
                exp_base=wait_settings.exp_base,
                initial=wait_settings.initial,
                max=wait_settings.max,
            )

        if wait_settings.policy == "fixed":
            return wait_fixed(wait_settings.fixed_wait)

        if wait_settings.policy == "incrementing":
            return wait_incrementing(
                start=wait_settings.increment_start,
                increment=wait_settings.increment_step,
                max=wait_settings.max,
            )

        if wait_settings.policy == "random":
            return wait_random(min=wait_settings.initial, max=wait_settings.max)

        if wait_settings.policy == "random_exponential":
            return wait_random_exponential(
                multiplier=wait_settings.initial, max=wait_settings.max
            )

        return wait_exponential(
            multiplier=wait_settings.initial,
            max=wait_settings.max,
            exp_base=wait_settings.exp_base,
        )


@lru_cache
def get_http_client() -> HttpxClient:
    from zee_api.core.config.settings import (
        get_app_settings,  # Delayed import to avoid circular dependency
    )

    settings = get_app_settings()

    return HttpxClient(settings.http_config)
