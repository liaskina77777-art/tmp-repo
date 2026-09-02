#!/usr/bin/env python3


import requests
import re
import sys

def count_links(url):
    #Подсчет уникальных ссылок на статьи Wikipedia
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        #Находим все ссылки на статьи
        pattern = r'href="(/wiki/[^":?#]+)"'
        matches = re.findall(pattern, response.text)
        
        #Фильтруем служебные страницы (содержат двоеточие)
        article_links = [m for m in matches if ':' not in m]
        
        #Убираем дубликаты
        unique_links = set(article_links)
        
        return len(unique_links)
        
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

def main():
    # Проверка аргументов командной строки
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        #Статья по умолчанию
        url = "https://en.wikipedia.org/wiki/Molecular_docking"
    
    print(f"Проверка статьи: {url}")
    count = count_links(url)
    
    if count is not None:
        print(f"\n Результаты:")
        print(f" Уникальных ссылок на статьи: {count}")

if __name__ == "__main__":
    main()
