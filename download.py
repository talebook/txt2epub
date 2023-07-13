#!/usr/bin/python3
#-*- coding: UTF-8 -*-

import sys
import click
import requests
from bs4 import BeautifulSoup

@click.command()
@click.option("-o", "--output", type=click.File('w', encoding='UTF-8'), default=sys.stdout, help="output text file")
@click.argument("site", default="https://www.ishuquge.org/txt/136189/")
def main(output, site):
    response = requests.get(site + "index.html")
    soup = BeautifulSoup(response.content, 'html.parser')

    title = soup.find("h2").text
    output.write(u"《%s》\n" % title)
    output.write(soup.select(".info .small")[0].get_text(separator="\n").replace("\n\n", "\n"))
    output.write(soup.select(".info .intro")[0].get_text(separator="\n").replace("\n\n", "\n"))

    links = []
    for link in reversed(soup.select(".listmain")[0].find_all('a')):
        href = link.get('href')
        if href in links: continue
        if href.endswith('.html'):
            links.append(href)

    links = list(reversed(links))

    for link in links:
        response = requests.get(site + link)
        soup = BeautifulSoup(response.content, 'html.parser')
        title = soup.find('h1').text
        content = soup.find('div', id='content').get_text(separator="\n")
        content = content.replace("\r", "")

        out = ["\n"]
        out.append(title)
        out.append(content)
        output.write("\n".join(out))

if __name__ == "__main__":
    main()
