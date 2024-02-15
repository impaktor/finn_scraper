"""
Scrape finn.no for adverts that fulfill my pickyness.

nUnlike finn's system, this:
- allows me to sort out adverts I've already seen
- search in radius from multiple different locations
- match/filter text in the advert body
- TODO: LLM to describe images, remove if:
  - floor is concrete, tiled, stone
  - windows small / basement
  - ceiling hight is low (as in basement)

Read documentation:
https://www.crummy.com/software/BeautifulSoup/bs4/doc/#css-selectors
other stuff:
https://stackoverflow.com/questions/34301815/understand-the-find-function-in-beautiful-soup
https://blog.hartleybrody.com/web-scraping/
or use: http://scrapy.org/

"""

import os
import pickle
import time

import requests
from bs4 import BeautifulSoup

is_debug = True


# meter radius to search:
radius = 3000
minprice = 7000
maxprice = 15500
seed_url = f"https://www.finn.no/realestate/lettings/search.html?area_from=34&lat=59.970230202946425&lon=10.782417360565233&price_from={minprice}&price_to={maxprice}&radius={radius}"


def parse_advert(url, isdebug=False):
    """Parse finn.no url advert; extract: body, price, livng area"""

    # time.sleep(4)

    response = requests.get(url)
    if response.status_code != 200:
        print(response.status_code)
        assert response.status_code == 200
    soup = BeautifulSoup(response.content, "html.parser")

    title = soup.find("h1", attrs={"class": "u-t2"}).text
    price = (
        soup.find("span", attrs={"class": "u-t3"})
        .text.replace(",-", "")
        .replace(r" ", "")
    )

    # Holds Primærrom,  Soverom,  Etasje, Boligtype, Leieperiode, Energimerking:
    info_box = soup.find(
        "dl", attrs={"class": "definition-list definition-list--inline"}
    )
    values = [i.text.strip() for i in info_box.find_all("dd")]
    keys = [i.text for i in info_box.find_all("dt")]
    inf = dict(zip(keys, values))

    body_box = soup.find("div", attrs={"class": "panel import-decoration"})

    # Throw away adverts mentioning any of (dont shy away from "kolletiv{tilbud,trafik}"):
    ban_words = [
        "korttidsleie",
        "korttidsutleie",
        "kortidsleie",  # felstavat?
        "kjeller leillehet",  # felstavat dubbelt upp?
        "kjeller leilighet",
        "kjellerleilighet",
        "kjeleleilihet",  # felstavat?
        "kjellerstue",
        "sokkeletasje",
        "søkkel Leilighet",  # felstavat?
        "sokkel leilighet",  # felstavat?
        "sokkell leilighet",  # felstavat?
        "sokkelleillighet",  # felstavat?
        "sokkelleilighet",
        "sokkel-leilighet",  # felstavat
        "sokkellleil",  # felstavat
        "sokkel leilighet",  # felstavat?
        "sokkeletage",
        "sokkelbolig",
        "bofellesskap",
        "bofelleskap",  # felstavat?
        "bokollektiv",
        "underetasjen",
        "underetasje",
        "u.etg",
        "fellesskap",
        "rom i bofellesskap",
    ]

    is_good = True
    try:
        body_text = body_box.find("p").text.strip().lower()
        text = inf["Boligtype"].lower() + " " + title.lower() + " " + body_text

        for word in ban_words:
            if text.find(word) != -1:
                is_good = False
                if isdebug:
                    print("\tfound word:", word)
    except Exception:
        pass

    if is_good:
        print("\t", "leie", price)
        for key in inf:
            print("\t", key, " ", inf[key])

    return is_good


def save(x, file_name=r"finn_scrape.sav"):
    "Save x to file (overwrites previous file)"

    # open the file for writing
    with open(file_name, "wb") as f:
        pickle.dump(x, f)


def load(file_name=r"finn_scrape.sav"):
    "Load previous processed adverts"

    if not os.path.exists(file_name):
        return {}

    # Load the object from the file into var b
    with open(file_name, "rb") as f:
        t = pickle.load(f)
        return t


def write2file(x, file_path="finn_nya_lägenhter.org"):
    "Write list x of urls to file, if not empty"
    if not x:
        return False
    with open(file_path, "w") as f:
        for e in x:
            f.write("%s\n" % e)
    print("wrote to %s" % file_path)
    return True


def main():

    # load previous search findings, to know which of the ones we find
    # are new
    old_results = load()  # where we store results of previous scrapings
    all_results = {}  # concat of current and old
    new_results = {}  # store new url's, that we haven't seen before

    global seed_url

    # Handwaivy: assume we only need to check first N-1 pages,
    # total counter * N adverts
    N = 4  # number of pages to go through
    counter = 50  # number of adverts per page
    urls = [seed_url + "&rows=%s&sort=1&page=%s" % (counter, i) for i in range(1, N)]

    i = 0
    for url in urls:
        print("Processing:\n" + url)

        response = requests.get(url)
        # print(response.status_code)
        soup = BeautifulSoup(response.content, "html.parser")

        # For each advert, this class type holds image, title, url, etc
        adverts = soup.find_all("div", attrs={"class": "ads__unit__content"})
        # adverts = soup.find_all('div', attrs={'class':'unit flex align-items-stretch result-item'})

        for ad in adverts:
            i += 1
            print("%s advert count" % i)

            # Find url to advert (assume I dont need a find_all())
            ad_url = "https://www.finn.no" + ad.find("a").get("href")
            if is_debug:
                print(ad_url)

            # Only process advert if we haven't seen it yet:
            if ad_url not in old_results:
                new_results[ad_url] = parse_advert(ad_url)
            else:
                print("skipping/already seen:", ad_url)

        # If next page of hits isn't fully populated, don't keep going:
        if counter > len(adverts):
            print(url)
            print(
                "\n\n---BREAK --- Counter: %s, adverts on page: %s\n\n"
                % (counter, len(adverts))
            )
            break

    # Concatenate, add new findings to old findings:
    for d in (new_results, old_results):
        all_results.update(d)

    results_good = [i for i in new_results if new_results[i]]
    results_bad = [i for i in new_results if not new_results[i]]

    print(
        "\nProcessed %s adverts, found %s new good & %s new crappy"
        % (i, len(results_good), len(results_bad))
    )
    print("new results: %s, all results: %s" % (len(new_results), len(all_results)))

    # save out new findings
    write2file(results_good)
    write2file(results_bad, "/tmp/nya_kassa_lgh.org")

    # save new (and old) as old:
    save(all_results)

    return 0


if __name__ == "__main__":
    main()
