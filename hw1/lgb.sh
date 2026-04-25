### Введение: 
#test 1
git commit -m v1
git commit -m v2
  
#test 2
git branch bugFix
git checkout bugFix

#test 3
git branch bugFix
git checkout bugFix
git commit -m v
git checkout main
git commit -m v2
git merge bugFix
  
#test 4
git checkout bugFix
git commit -m v1
git checkout main
git commit -m v2
git checkout bugFix
git rebase main

### Eдем дальше:

#test 1
git checkout c4
  
#test 2
git checkout bigFix

  
#test 3
git branch -f main c6
git checkout HEAD~1
git branch -f bugFix HEAD~1
  
#test 4
git branch -f local HEAD~1
git checkout pushed
git revert pushed

### Перемещаем труды туды-сюды

#test 1
git cherry-pick C3 C4 C7

#test 2
git rebase -i HEAD~4

### Сборная солянка

#test 1
git rebase -i main --solution-ordering C4
git rebase bugFix main

#test 2
git rebase -i HEAD~2 --solution-ordering C3,C2
git commit --amend
git rebase -i HEAD~2 --solution-ordering C2'',C3'

#test 3
git checkout main
gei cherry-pick C2
git commit --amend
git cherry-pick C3

#test 4
git tag v1 side~1
git tag v0 main~2
git checkout v1

#test 5

git commit

#Продвинутый уровень

#test_1
git rebase main bugFix
git rebase bugFix side
git rebase side another
git rebase another main

#test_2
git branch bugWork main^^2^

#test_3
git checkout one
git cherry-pick C4 C3 C2
git checkout two
git cherry-pick C5 C4 C3 C2
git branch -f three C2

#Удалённые репозитории
#push&pull

#test_1
git clone

#test_2
git commit 
git chechout o/main
git commit

#test_3
git fetch

#test_4
git pull

#test_5
git clone
git fakeTeamork 2
git commit
git pull

#test_6
git commit
git commit
git push

#test_7
git clone
git fakeTeamwork
git commit
git pull --rebase
git push

#test_8
git branch -f main o/main
git checkout -b feature C2
git push origin feature

#через origin - к звёздам

#test_1
git getch
git rebase o/main
git rebase side1 side2
gir rebase side2 side3
gir rebase side3 main
git push

#test_2
git checkout main
git pull
git merge side1
git merge side2
gir merge side3
git push

#test_3
git checkout -b side o/main
gir commit
git pull --rebase
git push

#test_4
git push origin main
git push origin foo

#test_5
git push origin main^:foo
git push origin foo:main

#test_6
git fetch origin c3:foo
git fetch origin c6:main
git chechout foo
git merge main

#test_7
git push origin :foo
git fetch origin :bar

#test_8
git pull origin c3:foo
git pull origin c2:side
