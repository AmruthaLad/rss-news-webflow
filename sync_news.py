import os
import json
import urllib.request
import urllib.error


WEBFLOW_TOKEN = os.environ["WEBFLOW_API_TOKEN"]
COLLECTION_ID = os.environ["WEBFLOW_COLLECTION_ID"]


WEBFLOW_COLLECTION_URL = (
    f"https://api.webflow.com/v2/collections/"
    f"{COLLECTION_ID}"
)


def webflow_request(
    method,
    url,
    data=None
):

    headers = {
        "Authorization": f"Bearer {WEBFLOW_TOKEN}",
        "Content-Type": "application/json",
        "Accept-Version": "1.0.0",
    }

    request = urllib.request.Request(
        url,
        method=method,
        headers=headers
    )

    if data is not None:
        request.data = json.dumps(
            data
        ).encode("utf-8")

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            return (
                response.status,
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        print(
            f"Webflow API error: {error.code}"
        )

        print(error_body)

        raise


def check_collection_schema():

    print("")
    print(
        "======================================"
    )

    print(
        "CHECKING WEBFLOW COLLECTION SCHEMA"
    )

    print(
        "======================================"
    )

    print(
        f"Collection ID: {COLLECTION_ID}"
    )

    print("")

    status, response = webflow_request(
        "GET",
        WEBFLOW_COLLECTION_URL
    )

    data = json.loads(response)

    fields = data.get(
        "fields",
        []
    )

    if not fields:

        print(
            "No fields were returned."
        )

        print("")
        print(
            "Full Webflow response:"
        )

        print(
            json.dumps(
                data,
                indent=2
            )
        )

        return

    print(
        f"Found {len(fields)} collection fields."
    )

    print("")

    for field in fields:

        print(
            "--------------------------------------"
        )

        print(
            f"Name: "
            f"{field.get('displayName')}"
        )

        print(
            f"Slug: "
            f"{field.get('slug')}"
        )

        print(
            f"Type: "
            f"{field.get('type')}"
        )

    print(
        "--------------------------------------"
    )

    print("")
    print(
        "Schema check completed."
    )


def main():

    print(
        "Starting Webflow collection check"
    )

    check_collection_schema()

    print("")
    print(
        "DONE"
    )


if __name__ == "__main__":
    main()
