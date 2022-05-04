import time
import os
import shutil
import unicodedata
import re
import getpass


print("Downloading the courses from Moralis Academy may be an illegal action.")
print("Please read Terms & Conditions carefully before proceeding.")
input("Enter to continue.")
print()


def error(package):
    print("Run:")
    print("pip install", package)


try:
    from vimeo_downloader import Vimeo
except:
    error("vimeo_downloader")
    exit(1)


try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
except:
    error("selenium")
    print("Then:")
    print("(1) Learn your Chrome version: Three dots > Help > About Google Chrome")
    print("(2) Find Chrome driver for this version at https://chromedriver.chromium.org/downloads, and download the one for your operating system.")
    print("(3) Extract the file content to somewhere mentioned in the environment variable named PATH.")
    exit(1)


try:
    from bs4 import BeautifulSoup
except:
    error("beautifulsoup4")
    exit(1)


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


def login(email, password):
    login_page = "https://academy.moralis.io/login-academy"

    driver = webdriver.Chrome()
    driver.get(login_page)

    bs = BeautifulSoup(driver.page_source, "html.parser")
    login_page_title = bs.find("title").text

    driver.find_element(By.ID, "user").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.NAME, "uael-login-submit").click()

    while True:
        time.sleep(1)
        bs = BeautifulSoup(driver.page_source, "html.parser")
        redirected_page_title = bs.find("title").text
        if login_page_title != redirected_page_title:
            break

    return driver


def extract_video_title(source):
    # source is from e.g. "https://academy.moralis.io/lessons/what-is-bitcoin" (after login)
    bs = BeautifulSoup(source, "html.parser")
    h1s = bs.find_all("h1")
    assert len(h1s) == 1
    return h1s[0].text  # e.g. "What is Bitcoin?"


def extract_video_url(source):
    # source is from e.g. "https://academy.moralis.io/lessons/what-is-bitcoin" (after login)
    bs = BeautifulSoup(source, "html.parser")
    iframes = bs.find_all("iframe")
    for iframe in iframes:
        if iframe.has_attr("src"):
            if iframe["src"].startswith("https://player.vimeo.com/video"):
                full_url = iframe["src"]
                return full_url[:full_url.index("?")]  # e.g. "https://player.vimeo.com/video/438334168"


def download_720p(video_url, page_url, dir, title=None):
    # No need to login.
    # Example:
    # video_url = "https://player.vimeo.com/video/438334168"
    # page_url = "https://academy.moralis.io/lessons/what-is-bitcoin"
    # download_720p(video_url, page_url, dir=".", title="what-is-bitcoin")
    
    v = Vimeo(video_url, embedded_on=page_url)
    for stream in v.streams:
        if stream.quality == "720p":
            stream.download(download_directory=dir, filename=title if title else v.metadata.title)
            break
    else:
        # 720p yoksa 720p'den daha iyi olan en düşük kalitedeki videoyu indir. Hiçbiri daha iyi değilse en iyisini indir.
        good_stream = v.streams[-1]
        for stream in reversed(v.streams):
            if stream.quality.endswith("p"):
                try:
                    current_quality = int(stream.quality[:-1])
                    if current_quality >= 720:
                        good_stream = stream
                except:
                    pass
        good_stream.download(download_directory=dir, filename=title if title else v.metadata.title)


def login_and_download_courses():

    def get_courses():
        filename = "courses.txt"
        file_path = filename
        if not os.path.exists(file_path):
            file_path = input("ERROR: courses.txt is not found. Please enter its path:")
            if os.path.isdir(file_path):
                file_path = file_path + os.sep + filename
        with open(file_path) as f:
            lines = f.read().splitlines()
        course_titles = []
        course_urls = []
        is_even = True
        for line in lines:
            if line.startswith("#"):
                continue
            if is_even:
                assert not line.startswith("http")
                line = line.replace("&", "and")
                line = slugify(line)
                course_titles.append(line.strip())
            else:
                assert line.startswith("http")
                course_urls.append(line.strip())
            is_even = not is_even
        assert len(course_titles) == len(course_urls)
        return course_titles, course_urls
        
    def extract_sections(driver, course_url, wait_for=10):
        sections = []

        page_no = 1
        while True:
            page_url = f"{course_url}?ld-lesson-page={page_no}"
            # e.g. https://academy.moralis.io/courses/eos-programming-101?ld-lesson-page=2

            driver.get(page_url)
            time.sleep(wait_for)

            source = driver.page_source
            bs = BeautifulSoup(source, "html.parser")

            items_elem = bs.select_one(".ld-item-list-items")
            if items_elem is None:
                break
            items = items_elem.findChildren(recursive=False)
            for child in items:
                classes = child.get("class")
                if "ld-item-list-section-heading" in classes:
                    section_name = child.select_one(".ld-lesson-section-heading").text.strip()
                    sections.append((section_name, []))
                elif "ld-item-list-item" in classes:
                    url = child.select_one("a")["href"]
                    sections[-1][1].append(url)
            page_no += 1

        return sections  # e.g. [("Section 1", ["url1", "url2"]), ("Section 2", ["url3"])]

    def choose_courses(course_titles, course_urls):
        print("Choose a course to download:")
        print(0, ") DOWNLOAD ALL", sep="")
        for index, (course_title, course_url) in enumerate(zip(course_titles, course_urls), 1):
            print(index, ") ", course_title, sep="")
        
        while True:
            try:
                choice = int(input("Choice: "))
                if 0 <= choice < len(course_titles):
                    break
            except:
                pass
        
        if choice == 0:
            course_titles_to_download = course_titles
            course_urls_to_download = course_urls
        else:
            course_titles_to_download = [course_titles[choice - 1]]
            course_urls_to_download = [course_urls[choice - 1]]
        
        return course_titles_to_download, course_urls_to_download

    print("Log in to Moralis Academy:")
    email = input("Email: ")
    password = getpass.getpass("Password (It will not be stored): ")
    print()
    main_path = os.getcwd() + os.sep + "courses"
    print(f"Courses will be downloaded into {main_path}.")

    driver = login(email, password)
    course_titles, course_urls = get_courses()
    course_titles_to_download, course_urls_to_download = choose_courses(course_titles, course_urls)
    
    for course_title, course_url in zip(course_titles_to_download, course_urls_to_download):
        print()
        print(course_title, "will be downloaded now.")

        sections = extract_sections(driver, course_url)
        
        dir_path = main_path + os.sep + course_title
        if os.path.exists(dir_path):
            input(f"{dir_path} already exists. Enter to delete it.")
            shutil.rmtree(dir_path)
        os.makedirs(dir_path)

        driver.get(course_url)
        source = driver.page_source

        with open(dir_path + os.sep + f"{course_title}.html", "w") as html:
            html.write(source)

        for section_no, section in enumerate(sections, 1):
            section_name = section[0]
            section_name = section_name.replace("&", "and")
            section_name = slugify(section_name)

            urls = section[1]
            section_dir_path = dir_path + os.sep + str(section_no) + "_" + section_name
            os.mkdir(section_dir_path)

            prev_video_title = None
            for video_no, url in enumerate(urls, 1):
                try:
                    driver.get(url)
                    source = driver.page_source
                    video_title = extract_video_title(source)
                    video_url = extract_video_url(source)

                    video_title = video_title.replace("&", "and")
                    video_title = slugify(video_title)

                    numbered_video_title = f"{video_no}_{video_title}"
                    download_720p(video_url, url, dir=section_dir_path, title=numbered_video_title)
                except Exception as e:
                    print()
                    print("It looks like there is no video on this page:", url)
                    print("Still I will save the HTML file.")
                    print()

                if video_title != prev_video_title:
                    with open(section_dir_path + os.sep + f"{video_no}_{video_title}.html", "w") as html:
                            html.write(source)
                prev_video_title = video_title


def main():
    login_and_download_courses()


if __name__ == "__main__":
    main()
