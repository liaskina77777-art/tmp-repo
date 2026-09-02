#!/usr/bin/env python3

import json
import argparse
import networkx as nx
import matplotlib.pyplot as plt
from typing import Dict, List


def load_graph(json_file: str) -> Dict[str, List[str]]:
    
#Загружает граф из JSON-файла и возвращает словарь 
    with open(json_file, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    return graph


def draw_graph(graph: Dict[str, List[str]], title: str = "Граф связей статей Википедии",
               output_file: str = "wiki_graph.png"):
    #Строит и сохраняет визуализацию графа.
    G = nx.Graph()   #неориентированный граф для визуализации

    #Добавляем узлы и рёбра
    for node, neighbors in graph.items():
        G.add_node(node)
        for neighbor in neighbors:
            if neighbor in graph:
                G.add_edge(node, neighbor)

    if len(G.nodes()) == 0:
        print("Граф пуст! Нет данных для отрисовки.")
        return

    #Настройка размера рисунка
    plt.figure(figsize=(16, 12))

    #Расположение узлов (spring layout)
    pos = nx.spring_layout(G, k=2, iterations=50)

    #Размер узлов пропорционален степени
    node_sizes = [G.degree(node) * 100 for node in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes,
                           node_color='lightblue', alpha=0.7)

    nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color='gray')

    nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')

    plt.title(f"{title}\nУзлов: {len(G.nodes())}, Рёбер: {len(G.edges())}",
              fontsize=14, fontweight='bold')

    plt.axis('off')                     #отключаем оси
    plt.tight_layout()                  #подгоняем поля
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Граф сохранён в {output_file}")

    # Показываем окно с графиком (опционально)
    plt.show()


def main():
    parser = argparse.ArgumentParser(description='Отрисовка графа связей статей Википедии')
    parser.add_argument('--json', required=True, help='Путь к JSON-файлу с графом')
    parser.add_argument('--output', default='wiki_graph.png',
                        help='Имя выходного файла с изображением (по умолчанию wiki_graph.png)')
    parser.add_argument('--title', default='Граф связей статей Википедии',
                        help='Заголовок графа')

    args = parser.parse_args()

    #Загружаем граф
    graph = load_graph(args.json)

    #Отрисовываем
    draw_graph(graph, args.title, args.output)

    #Дополнительная статистика
    G = nx.Graph()
    for node, neighbors in graph.items():
        G.add_node(node)
        for neighbor in neighbors:
            if neighbor in graph:
                G.add_edge(node, neighbor)

    print("\n" + "=" * 50)
    print("Статистика графа:")
    print(f"Количество узлов (статей): {G.number_of_nodes()}")
    print(f"Количество рёбер (связей): {G.number_of_edges()}")
    if G.number_of_nodes() > 0:
        print(f"Средняя степень узла: {2 * G.number_of_edges() / G.number_of_nodes():.2f}")
    if nx.is_connected(G):
        print(f"Диаметр (неориентированный): {nx.diameter(G)}")
    else:
        print("Граф несвязный (диаметр не определён).")
    print("=" * 50)


if __name__ == "__main__":
    main()

