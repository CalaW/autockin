import os

import requests

BASE_URL = "https://glados.cloud"
CHECKIN_URL = f"{BASE_URL}/api/user/checkin"
STATUS_URL = f"{BASE_URL}/api/user/status"

REFERER = f"{BASE_URL}/console/checkin"

HEADERS = {
    "Referer": REFERER,
    "Origin": BASE_URL,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

TIMEOUT = 15

# Known normal responses:
# - a new check-in
# - already checked in today
# - newer "observation logged" wording
NORMAL_CHECKIN_MESSAGES = (
    "checkin! got",
    "checkin repeats! please try tomorrow",
    "today's observation logged",
)


def request_json(method, url, *, cookie, json=None):
    response = requests.request(
        method,
        url,
        headers={
            **HEADERS,
            "Cookie": cookie,
        },
        json=json,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"{url} returned invalid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"{url} returned an unexpected JSON response"
        )

    return payload


def checkin(cookie):
    result = request_json(
        "POST",
        CHECKIN_URL,
        cookie=cookie,
        json={"token": "glados.cloud"},
    )

    message = str(result.get("message", "")).strip()
    normalized_message = message.lower()

    success = (
        result.get("code") == 0
        or any(
            marker in normalized_message
            for marker in NORMAL_CHECKIN_MESSAGES
        )
    )

    if not success:
        raise RuntimeError(
            f"Check-in was not successful: "
            f"code={result.get('code')!r}, message={message!r}"
        )

    return message


def get_status(cookie):
    result = request_json(
        "GET",
        STATUS_URL,
        cookie=cookie,
    )

    data = result.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(
            "Status response does not contain valid account data "
            "(the cookie may have expired)"
        )

    email = data.get("email")
    left_days = data.get("leftDays")

    if not email:
        raise RuntimeError(
            "Status response does not contain an email "
            "(the cookie may have expired)"
        )

    if left_days is None:
        raise RuntimeError(
            "Status response does not contain leftDays"
        )

    try:
        remaining_days = int(float(left_days))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid leftDays value: {left_days!r}"
        ) from exc

    return email, remaining_days


def run_account(cookie, index):
    message = checkin(cookie)
    email, remaining_days = get_status(cookie)

    print(
        f"Account {index}: {email}\n"
        f"Check-in: {message}\n"
        f"Remaining days: {remaining_days}\n"
    )


def main():
    raw_cookies = os.environ.get("COOKIES", "").strip()

    if not raw_cookies:
        print("::error::COOKIES secret is not configured")
        return 1

    cookies = [
        cookie.strip()
        for cookie in raw_cookies.split("&&")
        if cookie.strip()
    ]

    if not cookies:
        print("::error::No valid cookies found in COOKIES")
        return 1

    failures = []

    for index, cookie in enumerate(cookies, start=1):
        try:
            run_account(cookie, index)
        except Exception as exc:
            # Don't print the cookie itself.
            print(f"::error::Account {index} failed: {exc}")
            failures.append(index)

    if failures:
        print(
            f"{len(failures)}/{len(cookies)} account(s) failed: "
            + ", ".join(map(str, failures))
        )
        return 1

    print(f"All {len(cookies)} account(s) checked in successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
