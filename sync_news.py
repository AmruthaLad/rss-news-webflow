import os
import json
import urllib.request
import urllib.error


WEBFLOW_TOKEN = os.environ["WEBFLOW_API_TOKEN"]

# Trending News collection
COLLECTION_ID = "69b29bb5bd5023577d30cdf1"


def get_collection_schema():

    url = (
        f"https://api.webflow.com/v2/collections/"
        f"{COLLECTION_ID}"
    )

    headers = {
        "Authorization": f"Bearer {WEBFLOW_TOKEN}",
        "Content-Type": "application/json",
    }

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

            return data

    except urllib.error.HTTPError as error:

        print(
            f"Webflow API Error: {error.code}"
        )

        print(
            error.read().decode(
                "utf-8",
                errors="replace"
            )
        )

        return None


def main():

    print("")
    print(
        "======================================"
    )

    print(
        "CHECKING TRENDING NEWS COLLECTION"
    )

    print(
        "======================================"
    )

    print(
        f"Collection ID: {COLLECTION_ID}"
    )

    print("")

    data = get_collection_schema()

    if not data:
        return

    print(
        "FULL COLLECTION INFORMATION:"
    )

    print(
        json.dumps(
            data,
            indent=2
        )
    )

    print("")
    print(
        "======================================"
    )

    print(
        "FIELDS"
    )

    print(
        "======================================"
    )

    fields = data.get(
        "fields",
        []
    )

    for field in fields:

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


if __name__ == "__main__":
    main()
