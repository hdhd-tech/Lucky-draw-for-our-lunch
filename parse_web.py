#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import csv
import sys
import time
from typing import List, Dict, Optional

import requests
from lxml import etree
from urllib.parse import urljoin


def extract_shops(html_text: str) -> List[Dict[str, object]]:
    document = etree.HTML(html_text)
    if document is None:
        return []

    results: List[Dict[str, object]] = []

    # Each shop appears to be a <li> block that contains an <h4>
    for li in document.xpath('//li[.//h4]'):
        # Shop name
        name_list = li.xpath('.//h4/text()')
        if not name_list:
            continue
        name = name_list[0].strip()

        # Avg price: inside an <a class="mean-price"> ... <b>￥xx</b>
        avg_price_list = li.xpath('.//a[contains(@class, "mean-price")]//b/text()')
        avg_price = avg_price_list[0].strip() if avg_price_list else ''

        # Recommended dishes: <div class="recommend"> ... <a class="recommend-click">dish</a>
        dishes = [t.strip() for t in li.xpath('.//div[contains(@class, "recommend")]//a[contains(@class, "recommend-click")]/text()') if t.strip()]

        results.append({
            'name': name,
            'avg_price': avg_price,
            'recommended_dishes': dishes,
        })

    return results


def _format_cookies(cookies_str: str) -> Dict[str, str]:
    return {pair.split('=')[0].strip(): pair.split('=')[1].strip() for pair in cookies_str.split(';') if '=' in pair}


def load_html(url: str, cookies: Optional[str], timeout: int, session: Optional[requests.Session] = None, referer: Optional[str] = None) -> str:
    if not (url.lower().startswith('http://') or url.lower().startswith('https://')):
        raise ValueError('Only URL is supported. Please provide a valid http(s) URL.')

    headers = {
        'Host': 'www.dianping.com',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'sec-ch-ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
    headers['Referer'] = referer or 'https://www.dianping.com/'
    cookie_dict = _format_cookies(cookies) if cookies else None
    sess = session or requests.Session()
    last_err: Optional[Exception] = None
    for attempt in range(3):
        resp = sess.get(url, headers=headers, cookies=cookie_dict, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            text = resp.text
            if '身份核实' not in text:
                return text
            last_err = RuntimeError('身份核实页面，Cookie 可能无效或需要更新')
        elif resp.status_code in (403, 429):
            last_err = requests.HTTPError(f'{resp.status_code} Forbidden/Too Many Requests')
        else:
            last_err = requests.HTTPError(f'{resp.status_code} HTTP error')
        if attempt < 2:
            time.sleep(1.5 + attempt)
    if last_err:
        raise last_err
    raise RuntimeError('Unknown error fetching page')


def get_next_page_url(document: etree._Element, current_url: str) -> Optional[str]:
    # Try common patterns: class contains 'next' or link text contains '下一页'
    hrefs = document.xpath('//a[contains(@class, "next") or normalize-space(text())="下一页"]/@href')
    if not hrefs:
        return None
    next_href = hrefs[0]
    return urljoin(current_url, next_href)


def main() -> None:
    parser = argparse.ArgumentParser(description='Crawl Dianping list pages (auto pagination) to CSV (shop name, avg price, recommended dishes). If no args are provided, built-in defaults are used so you can just Run.')
    parser.add_argument('--url', default='https://www.dianping.com/shanghai/ch10/r854x81', help='Start URL (default: r992y40 示例页)')
    parser.add_argument('-o', '--output', default='Top meal.csv', help='Output CSV path (default: shops.csv)')
    parser.add_argument('--cookies', default='showNav=#nav-tab|0|0; navCtgScroll=0; logan_session_token=7aw9w02k3pscdu6wg1m8; _lxsdk_cuid=1988901cf06c8-00061143077b7-4c657b58-11cc40-1988901cf06c8; _lxsdk=1988901cf06c8-00061143077b7-4c657b58-11cc40-1988901cf06c8; _hc.v=0d606b56-0d4f-f07c-0e0e-88278b62e936.1754645254; fspop=test; s_ViewType=10; utm_source_rg=; qruuid=ea58ae97-24b2-4b4c-86c5-68d76875235e; WEBDFPID=7z2298w2w81w51290u937u6zu55w59188011098vww2979589711z625-1754731661610-1754645260905WSIGYOIfd79fef3d01d5e9aadc18ccd4d0c95073468; dplet=9d6e262fb9eaf437fe33ff6a7af57bb3; dper=020215214dadbd52bfcacab414b82ae60340ad8092a50da8a909f1df75f91593e8778228af4802e3d6de4b565ba821183146b542509bd7a3527400000000ab2b000086fe541e04ad53505dd785372a776666b1e07e6eba19ebc763921e417ba9bd6e5f6f209f55fc12606fd8bc34fa72638d; ll=7fd06e815b796be3df069dec7836c3df; ua=Praj; ctu=d5c796a981d851567eeff61a0b69a898a5a3c485c06795911dce15831ecb0b85; Hm_lvt_602b80cf8079ae6591966cc70a3940e7=1754645315; HMACCOUNT=4153CA8ECBEDA100; Hm_lpvt_602b80cf8079ae6591966cc70a3940e7=1754645366; _lxsdk_s=1988901cf06-aaa-877-d45%7C%7C157', help='Cookie header string for requests (建议填写登录后 Cookie)')
    parser.add_argument('--timeout', type=int, default=60, help='Request timeout seconds (default: 20)')
    parser.add_argument('--max-pages', type=int, default=0, help='Max pages to crawl (0 means no explicit limit until no next page)')
    parser.add_argument('--sleep', type=float, default=0.0, help='Sleep seconds between pages (default: 0)')
    args = parser.parse_args()

    session = requests.Session()
    current_url = args.url
    page_index = 0
    # write CSV header once

    with open(args.output, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'avg_price', 'recommended_dishes'])

        while current_url:
            page_index += 1
            # Use previous page as Referer to mimic browser navigation
            referer = 'https://www.dianping.com/' if page_index == 1 else prev_url
            html_text = load_html(current_url, args.cookies, args.timeout, session=session, referer=referer)
            # Quick guard for identity verification page
            if '身份核实' in html_text:
                raise RuntimeError('Hit identity verification page. Provide valid logged-in cookies with --cookies.')

            shops = extract_shops(html_text)
            for s in shops:
                dishes_joined = '、'.join(s['recommended_dishes']) if s['recommended_dishes'] else ''
                writer.writerow([s['name'], s['avg_price'], dishes_joined])

            if args.max_pages and page_index >= args.max_pages:
                break

            doc = etree.HTML(html_text)
            if doc is None:
                break
            prev_url = current_url
            next_url = get_next_page_url(doc, current_url)
            if not next_url or next_url == current_url:
                break
            current_url = next_url
            if args.sleep > 0:
                time.sleep(args.sleep)


if __name__ == '__main__':
    main()


