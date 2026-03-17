1) nano complement.py - создаём файл 
2) вставляем туда код для рассчёта reverse_complement и GC-состава:

"""
#!/usr/bin/env python3

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

"""
3) делаем файл исполняемым: chmod +x complement.py
4) делаем первый коммит:
git add hw1/complement.py
git commit -m "hw1: add complement.py with basic functionality"(коммит 8f31bdd)
5) далее сделала второй коммит: 
git add hw1/README.md
git commit -m "hw11: add README with description"(коммит 6с61165)
6) также у меня были неудачные коммиты:
git commit -m "hw11"
git commit -m "hw12"
7) git push - для отправки коммита
8) для проверки состояния я также использовала 3 команды: 
git status
git log --oneline
git log --oneline --branches --remotes --graph
