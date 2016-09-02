import requests
from BeautifulSoup import BeautifulSoup
import string
import base64
rot13 = string.maketrans(
    "ABCDEFGHIJKLMabcdefghijklmNOPQRSTUVWXYZnopqrstuvwxyz",
    "NOPQRSTUVWXYZnopqrstuvwxyzABCDEFGHIJKLMabcdefghijklm")


def get_proxy_list():
    response = requests.get("http://www.cool-proxy.net/proxies/http_proxy_list/sort:response_time_average/direction:asc/country_code:/port:/anonymous:1")
    proxies = []
    if response.status_code == 200:
        try:
            html = response.content
            parsed_html = BeautifulSoup(html)
            proxies_body = parsed_html.body.findAll('tr')
            first = True
            for child in proxies_body:
                if first:
                    first = False
                    continue

                settings = child.findAll('td')
                if len(settings) > 0:
                    try:
                        encoded_ip = settings[0].text
                        proxies.append('%s:%s' % (base64.decodestring(string.translate(str(encoded_ip.split('str_rot13("')[1][:-4]), rot13)), str(settings[1].text)))
                    except:
                        pass
            return proxies
        except:
            pass
        return proxies

