import os
import re
import html
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import timezone


RSS_URL = os.environ["RSS_FEED_URL"]
WEBFLOW_TOKEN = os.environ["WEBFLOW_API_TOKEN"]
COLLECTION_ID = os.environ["WEBFLOW_COLLECTION_ID"]
SITE_ID = os.environ["WEBFLOW_SITE_ID"]

WEBFLOW_ITEMS_URL = (
    f"https://api.webflow.com/v2/collections/"
    f"{COLLECTION_ID}/items"
)

WEBFLOW_PUBLISH_URL = (
    f"https://api.webflow.com/v2/sites/"
    f"{SITE_ID}/publish"
)


def fetch_rss():
    print("Reading RSS feed...")

    request = urllib.request.Request(
        RSS_URL,
        headers={
            "User-Agent": "RSS-News-Webflow-Automation/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:
        return response.read()


def clean_text(value):
    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", "", value)

    return " ".join(value.split()).strip()


def parse_rss(data):
    root = ET.fromstring(data)

    articles = []

    for item in root.findall(".//item"):

        title = clean_text(
            item.findtext("title")
        )

        link = clean_text(
            item.findtext("link")
        )

        pub_date = clean_text(
            item.findtext("pubDate")
        )

        if not title or not link:
            continue

        articles.append(
            {
                "title": title,
                "link": link,
                "pub_date": pub_date,
            }
        )

    return articles


def convert_date(date_string):

    if not date_string:
        return ""

    try:

        date = parsedate_to_datetime(
            date_string
        )

        if date.tzinfo is not None:
            date = date.astimezone(
                timezone.utc
            )

        return date.strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

    except Exception as error:

        print(
            f"Date conversion failed: {error}"
        )

        return ""


def get_source(link):

    if "venturebeat.com" in link:
        return "VentureBeat"

    if "techcrunch.com" in link:
        return "TechCrunch"

    if "intelligentautomation.network" in link:
        return "Intelligent Automation Network"

    if "artificialintelligence-news.com" in link:
        return "Artificial Intelligence News"

    if "diginomica.com" in link:
        return "Diginomica"

    if "cio.com" in link:
        return "CIO"

    return "News"


def create_slug(title):

    slug = title.lower()

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        slug
    )

    slug = slug.strip("-")

    return slug[:90]


def webflow_request(
    method,
    url,
    data=None
):

    headers = {
        "Authorization":
            f"Bearer {WEBFLOW_TOKEN}",
        "Content-Type":
            "application/json",
        "Accept-Version":
            "1.0.0",
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
                response.read().decode(
                    "utf-8"
                )
            )

    except urllib.error.HTTPError as error:

        error_body = error.read().decode(
            "utf-8",
            errors="replace"
        )

        print(
            f"Webflow API error: "
            f"{error.code}"
        )

        print(error_body)

        raise


def create_cms_item(article):

    title = article["title"]
    link = article["link"]
    pub_date = article["pub_date"]

    source = get_source(link)

    slug = create_slug(title)

    webflow_date = convert_date(
        pub_date
    )

    field_data = {
        "name": title,
        "slug": slug,
        "news-url": link,
        "source": source,
        "publish-date": webflow_date,
    }

    payload = {
        "isArchived": False,
        "isDraft": False,
        "fieldData": field_data,
    }

    status, response = webflow_request(
        "POST",
        WEBFLOW_ITEMS_URL,
        payload
    )

    print(
        f"Created Webflow item: {status}"
    )


def publish_site():

    print("")
    print("Publishing Webflow site...")

    payload = {
        "publishToWebflowSubdomain": True
    }

    try:

        status, response = webflow_request(
            "POST",
            WEBFLOW_PUBLISH_URL,
            payload
        )

        print(
            f"Webflow publish response: "
            f"{status}"
        )

        print(
            "Webflow site publish request "
            "completed."
        )

    except urllib.error.HTTPError:

        print(
            "Webflow publishing failed."
        )


def main():

    print(
        "Starting RSS → Webflow sync"
    )

    print(
        f"Collection ID: {COLLECTION_ID}"
    )

    print(
        f"Site ID: {SITE_ID}"
    )

    rss_data = fetch_rss()

    articles = parse_rss(
        rss_data
    )

    print(
        f"Found {len(articles)} "
        f"RSS articles"
    )

    if not articles:

        print(
            "No RSS articles found."
        )

        return

    # Process latest 10 articles
    articles = articles[:10]

    created_count = 0

    for article in articles:

        print("")
        print(
            "----------------------------"
        )

        print(
            f"Title: {article['title']}"
        )

        print(
            f"Source: "
            f"{get_source(article['link'])}"
        )

        print(
            f"URL: {article['link']}"
        )

        print(
            f"RSS Date: "
            f"{article['pub_date']}"
        )

        print(
            "----------------------------"
        )

        try:

            create_cms_item(
                article
            )

            created_count += 1

        except urllib.error.HTTPError:

            print(
                "Could not create this item."
            )

    print("")
    print(
        f"Created {created_count} "
        f"new CMS items."
    )

    if created_count > 0:

        publish_site()

    print("")
    print(
        "RSS → Webflow sync finished."
    )


if __name__ == "__main__":
    main()
