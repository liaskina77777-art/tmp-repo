#!/usr/bin/env python3
"""
Генератор данных для предсказания взаимодействия РНК и белка.
Создает JSON файл с 20 белками и 40 случайными мотивами РНК для каждого.
"""

import json
import random
import csv
import os
from typing import Dict, List

# Список 20 белков ENCODE (реальные мнемоники)
PROTEINS = [
    "EZH2", "SUZ12", "CTCF", "RAD21", "SMC3", "POL2", "H3K4me3", "H3K27ac",
    "H3K4me1", "H3K36me3", "H3K9me3", "H3K27me3", "BRD4", "MED1", "MAX",
    "MYC", "P300", "TAF1", "YY1", "RBPJ"
]

# Алфавит РНК/ДНК
ALPHABET = ['A', 'T', 'G', 'C']

# Фиксированный seed для воспроизводимости
RANDOM_SEED = 42

def generate_random_motif(length: int) -> str:
    """Генерирует случайный мотив заданной длины."""
    return ''.join(random.choice(ALPHABET) for _ in range(length))

def generate_dataset(proteins: List[str], 
                     motifs_per_protein: int = 40,
                     min_motif_len: int = 3,
                     max_motif_len: int = 9,
                     output_file: str = "data/rna_protein_scores.json",
                     output_csv: str = "data/rna_protein_scores.csv") -> Dict:
    """
    Генерирует датасет с белками и их мотивами.
    
    Args:
        proteins: список белков
        motifs_per_protein: количество мотивов на белок
        min_motif_len: минимальная длина мотива
        max_motif_len: максимальная длина мотива
        output_file: путь для сохранения JSON
        output_csv: путь для сохранения CSV
    
    Returns:
        Dict: словарь с данными
    """
    # Устанавливаем seed для воспроизводимости
    random.seed(RANDOM_SEED)
    
    dataset = {}
    csv_rows = []
    
    for protein in proteins:
        motifs = {}
        # Генерируем уникальные мотивы для каждого белка
        used_motifs = set()
        
        while len(motifs) < motifs_per_protein:
            length = random.randint(min_motif_len, max_motif_len)
            motif = generate_random_motif(length)
            
            # Избегаем дубликатов мотивов для одного белка
            if motif not in used_motifs:
                used_motifs.add(motif)
                # Генерируем случайный скор от -1 до 1
                score = round(random.uniform(-1, 1), 4)
                motifs[motif] = score
                csv_rows.append([protein, motif, score])
        
        dataset[protein] = motifs
    
    # Создаем директорию если её нет
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Сохраняем в JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    # Сохраняем в CSV
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['protein', 'motif', 'score'])
        writer.writerows(csv_rows)
    
    print(f"Dataset saved to {output_file} and {output_csv}")
    print(f"Total proteins: {len(dataset)}")
    print(f"Total motifs: {sum(len(motifs) for motifs in dataset.values())}")
    
    return dataset

def load_dataset(json_path: str = "data/rna_protein_scores.json") -> Dict:
    """Загружает датасет из JSON файла."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

if __name__ == "__main__":
    generate_dataset(PROTEINS)
