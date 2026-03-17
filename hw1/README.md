# ДЗ_1: работа с Git
## TASK_2

## Блок заданий 1-3

1. *nano complement.py* - создаём файл
2. вставляем туда код для рассчёта reverse_complement и GC-состава:

```
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
  ```
    
3. делаем файл исполняемым: *chmod +x complement.py*
4. делаем первый коммит:
*git add hw1/complement.py*
*git commit -m "hw1: add complement.py with basic functionality"*(коммит 8f31bdd)
5. далее сделала второй коммит:
*git add hw1/README.md*
*git commit -m "hw11: add README with description"*(коммит 6с61165)
6. также у меня были неудачные коммиты:
*git commit -m "hw11"*
*git commit -m "hw12"*
7. *git push* - для отправки коммита
8. для проверки состояния я также использовала 3 команды:
*git status*
*git log --oneline*
*git log --oneline --branches --remotes --graph*

## Задание 4

9. Создала временный файл: *touch hw1/temp.txt*
10. add(добавить в git):
    
*git add hw1/temp.txt*
*git commit -m "hw1: add temp file for testing"*

mv(переименовать):
*git mv hw1/temp.txt hw1/test.txt*
*git commit -m "hw1: rename temp.txt to test.txt"*

rm(удаление):
*git rm hw1/test.txt*
*git commit -m "hw1: remove test file"*

Отправила изменения на GitHub: *git push*

## Задание 5

11. Сначала добавляю тэг - *git tag task1*
потом отправляю тэг на Git: *git push origin task1*
потом проверила, создался ли этот тэг: *git tag --list*

## Задание 6

В директории hw1 хранятся 2 файла:

**complement.py** - скрипт для вычисления reverse_complement и GC состава
**README.md** - файл с описанием
