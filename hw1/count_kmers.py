#!/usr/bin/env python3

import json
import sys
import argparse
from collections import defaultdict

def read_fasta(filename):
    sequences = {}
    current_seq = ""
    current_header = ""
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if current_header:
                    sequences[current_header] = current_seq
                current_header = line[1:]  # убираем '>'
                current_seq = ""
            else:
                current_seq += line
        if current_header:
            sequences[current_header] = current_seq
    
    return sequences

def count_kmers(sequence, k=2):
    kmers = defaultdict(int)
    for i in range(len(sequence) - k + 1):
        kmer = sequence[i:i+k]
        kmers[kmer] += 1
    return dict(kmers)

def main():
    parser = argparse.ArgumentParser(description='Подсчёт k-меров в FASTA файле')
    parser.add_argument('--fa', required=True, help='Входной FASTA файл')
    parser.add_argument('--k', type=int, default=2, help='Длина k-мера (по умолчанию: 4)')
    parser.add_argument('--out', default='cnts.json', help='Выходной JSON файл')

    args = parser.parse_args()
    
    sequences = read_fasta(args.fa)
    
    result = {}
    for header, seq in sequences.items():
        result[header] = count_kmers(seq, k=2)
    
    with open('cnts.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Результат сохранён в cnts.json")

if __name__ == "__main__":
    main()

