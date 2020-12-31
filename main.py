import os
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import StaleElementReferenceException
from bs4 import BeautifulSoup

import csv
import ssl
from urllib.request import urlopen
from urllib.parse import quote_plus

options = webdriver.ChromeOptions()
options.add_argument('headless')
options.add_argument('lang=ko_KR')
chromedriver_path = "/chromdriver/chromedriver"
driver = webdriver.Chrome(os.path.join(os.getcwd(), chromedriver_path), options=options)  # chromedriver 열기


def main():
    global driver, load_wb, review_num

    driver.implicitly_wait(4)  # 렌더링 될때까지 기다린다 4초
    driver.get('https://map.kakao.com/')  # 주소 가져오기

    # 검색할 목록
    place_infos = ['맛집']

    for i, place in enumerate(place_infos):
        # delay
        if i % 4 == 0 and i != 0:
            sleep(5)
        print("#####", i)
        search(place)

    driver.quit()
    print("finish")


def search(place):
    global driver

    search_area = driver.find_element_by_xpath('//*[@id="search.keyword.query"]')  # 검색 창
    search_area.send_keys(place)  # 검색어 입력
    driver.find_element_by_xpath('//*[@id="search.keyword.submit"]').send_keys(Keys.ENTER)  # Enter로 검색
    sleep(1)

    # 검색된 정보가 있는 경우에만 탐색
    # 1번 페이지 place list 읽기
    html = driver.page_source

    soup = BeautifulSoup(html, 'html.parser')
    place_lists = soup.select('.placelist > .PlaceItem')  # 검색된 장소 목록
    # place_lists = soup.select('.placelist') # 검색된 장소 목록

    # 검색된 첫 페이지 장소 목록 크롤링하기
    crawling(place, place_lists)
    search_area.clear()

    # 우선 더보기 클릭해서 2페이지
    try:
        driver.find_element_by_xpath('//*[@id="info.search.place.more"]').send_keys(Keys.ENTER)
        sleep(1)

        # 2~ 5페이지 읽기
        for i in range(2, 6):
            # 페이지 넘기기
            xPath = '//*[@id="info.search.page.no' + str(i) + '"]'
            driver.find_element_by_xpath(xPath).send_keys(Keys.ENTER)
            sleep(1)

            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            place_lists = soup.select('.placelist > .PlaceItem')  # 장소 목록 list
            # place_lists = soup.select('.placelist') # 장소 목록 list
            crawling(place, place_lists)

    except ElementNotInteractableException:
        print('not found')
    finally:
        search_area.clear()

def crawling(place, place_lists):
    """
    페이지 목록을 받아서 크롤링 하는 함수
    :param place: 리뷰 정보 찾을 장소이름
    """

    ad_flg = 0

    while_flag = False
    for i, place in enumerate(place_lists):
        # 광고에 따라서 index 조정해야함
        # if i >= 6:
        i = i + ad_flg;

        place_name = place.select('.head_item > .tit_name > .link_name')[0].text  # place name
        place_address = place.select('.info_item > .addr > p')[0].text  # place address
        try:
            detail_page_xpath = '//*[@id="info.search.place.list"]/li[' + str(i + 1) + ']/div[5]/div[4]/a[1]'
            print("up")
            driver.find_element_by_xpath(detail_page_xpath).send_keys(Keys.ENTER)
            print("down")
            driver.switch_to.window(driver.window_handles[-1])  # 상세정보 탭으로 변환
            sleep(1)

            print('####', place_name)

            # 첫 페이지
            extract_review(place_name,place_address)

            # 2-5 페이지
            idx = 3
            try:
                page_num = len(driver.find_elements_by_class_name('link_page'))  # 페이지 수 찾기
                for i in range(page_num - 1):
                    # css selector를 이용해 페이지 버튼 누르기
                    driver.find_element_by_css_selector(
                        '#mArticle > div.cont_evaluation > div.evaluation_review > div > a:nth-child(' + str(
                            idx) + ')').send_keys(Keys.ENTER)
                    sleep(1)
                    extract_review(place_name,place_address)
                    idx += 1
                driver.find_element_by_link_text('다음').send_keys(Keys.ENTER)  # 5페이지가 넘는 경우 다음 버튼 누르기
                sleep(1)
                extract_review(place_name,place_address)  # 리뷰 추출
            except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
                print("no review in crawling 1")
                break
            # 그 이후 페이지
            while True:
                idx = 4
                try:
                    page_num = len(driver.find_elements_by_class_name('link_page'))
                    for i in range(page_num - 1):
                        driver.find_element_by_css_selector(
                            '#mArticle > div.cont_evaluation > div.evaluation_review > div > a:nth-child(' + str(
                                idx) + ')').send_keys(Keys.ENTER)
                        sleep(1)
                        extract_review(place_name,place_address)
                        idx += 1
                    driver.find_element_by_link_text('다음').send_keys(Keys.ENTER)  # 10페이지 이상으로 넘어가기 위한 다음 버튼 클릭
                    sleep(1)
                    extract_review(place_name,place_address)  # 리뷰 추출
                except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
                    print("no review in crawling 2")
                    break

            driver.close()
            driver.switch_to.window(driver.window_handles[0])  # 검색 탭으로 전환
        except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
            print("Ad Item")
            ad_flg = ad_flg + 1;


def extract_review(place_name,place_address):
    global driver

    ret = True

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    total = soup.select('.api_txt_lines.total_tit')
    searchList = []

    # 첫 페이지 리뷰 목록 찾기
    review_lists = soup.select('.list_evaluation > li')
    #리뷰가 있는 경우
    if len(review_lists) != 0:
        for i, review in enumerate(review_lists):
            comment = review.select('.txt_comment > span') # 리뷰
            rating = review.select('.grade_star > em') # 별점
            val = ''
            if len(rating) != 0:
                val = place_name + ',' + place_address + ',' + comment[0].text + ',' + rating[0].text.replace('점', '')
            else:
                val = comment[0].text + '/0'
            print(val)
            with open('맛집.csv', 'a', encoding='utf-8', newline='')as writer_csv:
                writer = csv.writer(writer_csv, delimiter=',')
                writer.writerow([val])
    else:
        print('no review in extract')
        ret = False
    return ret


if __name__ == "__main__":
    main()
