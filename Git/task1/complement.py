#!/usr/bin/env python3
"""
Вычисляет reverse complement и GC-состав ДНК-последовательности.

"""

import argparse

def reverse_complement(seq):
    comp = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G',
            'a': 't', 't': 'a', 'g': 'c', 'c': 'g'}
    return ''.join(comp.get(base, base) for base in reversed(seq))

def gc_content(seq):
    seq = seq.upper()
    if not seq:
        return 0.0
    return (seq.count('G') + seq.count('C')) / len(seq)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seq', required=True, help='DNA sequence')
    args = parser.parse_args()

    print(reverse_complement(args.seq))
    print(f"{gc_content(args.seq):.3f}")

if __name__ == "__main__":
    main()
