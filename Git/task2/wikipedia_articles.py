#!/usr/bin/env python3


import argparse
import json
import re
import sys
import logging
from typing import Dict, Set, List, Tuple
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class WikipediaCrawler:
    
    BASE_URL = "https://en.wikipedia.org"
    HEADERS = {
        "User-Agent": "EducationalCrawler/1.0 (contact: student@example.edu)"
    }
    
    def __init__(self, start_url: str, depth: int = 2):
       
        self.start_url = start_url
        self.depth = depth
        self.graph: Dict[str, Set[str]] = {}  # {article_title: set(linked_titles)}
        self.visited: Set[str] = set()  # посещённые статьи (по title)
        
        # Настройка сессии с повторными попытками
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        session = requests.Session()
        
        # Настройка повторных попыток
        retry_strategy = Retry(
            total=3,  # максимальное количество повторных попыток
            backoff_factor=1,  # задержка между попытками: 1, 2, 4 секунды
            status_forcelist=[429, 500, 502, 503, 504],  # коды ответов для повторных попыток
            allowed_methods=["GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update(self.HEADERS)
        
        return session
    
    def extract_article_title(self, url: str) -> str:
       
        # Извлекаем часть после /wiki/
        match = re.search(r'/wiki/([^?#]+)', url)
        if match:
            title = match.group(1)
            # Заменяем подчёркивания на пробелы
            title = title.replace('_', ' ')
            # URL-декодируем
            title = title.replace('%28', '(').replace('%29', ')')
            return title
        return url
    
    def is_wikipedia_article(self, url: str) -> bool:
      
        # Проверяем, что это ссылка на английскую Википедию
        if not url.startswith("/wiki/") and not url.startswith(self.BASE_URL + "/wiki/"):
            return False
        
        # Извлекаем путь
        if url.startswith(self.BASE_URL):
            path = url[len(self.BASE_URL):]
        else:
            path = url
        
        # Проверяем, что это статья (не содержит двоеточий в пути после /wiki/)
        # Исключаем служебные страницы: Special:, Help:, File:, Template:, и т.д.
        if re.search(r'/wiki/([^:]+:)', path):
            return False
        
        # Исключаем ссылки с якорями (они ведут на ту же страницу)
        if '#' in path:
            return False
        
        return True
    
    def get_article_links(self, url: str) -> List[str]:
     
        try:
            # Формируем полный URL, если передан относительный
            full_url = urljoin(self.BASE_URL, url)
            
            logger.info(f"Fetching: {full_url}")
            
            response = self.session.get(
                full_url,
                timeout=15  # увеличил таймаут до 15 секунд
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Находим основной контент страницы
            content = soup.find('div', id='bodyContent')
            if content is None:
                logger.warning(f"No bodyContent found for {full_url}")
                return []
            
            # Паттерн для ссылок на статьи
            pattern = re.compile(r'^/wiki/((?!:).)*$')
            
            links = []
            for link in content.find_all('a', href=pattern):
                href = link.get('href')
                if href and self.is_wikipedia_article(href):
                    # Преобразуем в полный URL для единообразия
                    full_link = urljoin(self.BASE_URL, href)
                    links.append(full_link)
            
            # Удаляем дубликаты, сохраняя порядок
            unique_links = []
            seen = set()
            for link in links:
                if link not in seen:
                    seen.add(link)
                    unique_links.append(link)
            
            logger.info(f"Found {len(unique_links)} links in '{self.extract_article_title(url)}'")
            
            return unique_links
            
        except requests.Timeout:
            logger.error(f"Timeout error fetching {full_url}")
            return []
        except requests.RequestException as e:
            logger.error(f"Error fetching {full_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error processing {full_url}: {e}")
            return []
    
    def get_article_title_from_url(self, url: str) -> str:
        return self.extract_article_title(url)
    
    def crawl(self) -> Dict[str, List[str]]:
        
        # Очередь для BFS: (url, current_depth)
        queue: List[Tuple[str, int]] = [(self.start_url, 0)]
        processed_count = 0
        failed_urls = []
        
        logger.info(f"Starting crawl from: {self.extract_article_title(self.start_url)}")
        logger.info(f"Max depth: {self.depth}")
        logger.info("-" * 50)
        
        while queue:
            url, current_depth = queue.pop(0)
            
            # Получаем название статьи
            title = self.get_article_title_from_url(url)
            
            # Пропускаем, если уже посещали
            if title in self.visited:
                continue
            
            processed_count += 1
            logger.info(f"[{processed_count}] Processing (depth {current_depth}): {title}")
            
            # Отмечаем как посещённую
            self.visited.add(title)
            
            # Инициализируем список связей в графе
            if title not in self.graph:
                self.graph[title] = set()
            
            # Получаем ссылки со страницы
            links = self.get_article_links(url)
            
            if not links and current_depth < self.depth:
                logger.warning(f"No links found for {title}, but depth {current_depth} < {self.depth}")
            
            for link_url in links:
                link_title = self.get_article_title_from_url(link_url)
                # Добавляем связь в граф
                self.graph[title].add(link_title)
                
                # Если не достигли максимальной глубины и страница ещё не посещена,
                # добавляем в очередь для дальнейшего обхода
                if current_depth < self.depth and link_title not in self.visited:
                    queue.append((link_url, current_depth + 1))
            
            # Небольшая задержка, чтобы не перегружать сервер
            time.sleep(0.3)  # уменьшил задержку для скорости
        
        # Логируем статистику по неудачным загрузкам
        if failed_urls:
            logger.warning(f"Failed to fetch {len(failed_urls)} URLs")
            for url in failed_urls[:5]:  # показываем только первые 5
                logger.warning(f"  - {url}")
        
        # Преобразуем множества в списки для JSON-сериализации
        result = {title: sorted(list(links)) for title, links in self.graph.items()}
        return result
    
    def save_graph(self, output_file: str) -> Dict[str, List[str]]:
        graph_data = self.crawl()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"Graph saved to: {output_file}")
        logger.info(f"Total articles: {len(graph_data)}")
        logger.info(f"Total connections: {sum(len(links) for links in graph_data.values())}")
        logger.info(f"{'='*50}")
        
        return graph_data


def main():
    parser = argparse.ArgumentParser(
        description='Веб-кроулер для Wikipedia. Собирает граф связей между статьями.'
    )
    parser.add_argument(
        '--url',
        type=str,
        required=True,
        help='URL начальной статьи (например, https://en.wikipedia.org/wiki/Python)'
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=2,
        help='Глубина обхода (по умолчанию: 2)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.3,
        help='Задержка между запросами в секундах (по умолчанию: 0.3)'
    )
    
    args = parser.parse_args()
    
    # Извлекаем название статьи для имени выходного файла
    temp_crawler = WikipediaCrawler(args.url, args.depth)
    title = temp_crawler.get_article_title_from_url(args.url)
    # Очищаем название для имени файла (убираем пробелы и спецсимволы)
    safe_title = re.sub(r'[\\/*?:"<>|]', '', title).replace(' ', '_')
    output_file = f"{safe_title}.json"
    
    logger.info(f"Starting Wikipedia crawler")
    logger.info(f"Start article: {title}")
    logger.info(f"Depth: {args.depth}")
    logger.info(f"Output file: {output_file}")
    
    # Запускаем кроулер
    crawler = WikipediaCrawler(args.url, args.depth)
    crawler.save_graph(output_file)
    
    logger.info("\nCrawling completed successfully!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nCrawling interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
