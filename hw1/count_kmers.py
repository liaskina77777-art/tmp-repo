#!/usr/bin/env python3
import argparse
import json

def read_fasta(filename):
    sequences = {}
    with open(filename) as f:
        name = None
        seq = []
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if name:
                    sequences[name] = ''.join(seq)
                name = line[1:]
                seq = []
            else:
                seq.append(line)
        if name:
            sequences[name] = ''.join(seq)
    return sequences

def count_kmers(seq, k=4):
    kmers = {}
    for i in range(len(seq) - k + 1):
        kmer = seq[i:i+k]
        kmers[kmer] = kmers.get(kmer, 0) + 1
    return kmers

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fa', required=True, help='input FASTA file')
    args = parser.parse_args()

    seqs = read_fasta(args.fa)
    result = {}
    for name, seq in seqs.items():
        result[name] = count_kmers(seq, k=4)

    with open('cnts.json', 'w') as f:
        json.dump(result, f, indent=2)

if __name__ == '__main__':
    main()
