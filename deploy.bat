@echo off
echo 🚀 Flask 앱 Render 배포 자동화 시작...

:: 1. test_ 로 시작하는 파일들 제거
echo 🔍 불필요한 파일 삭제 중...
del test_*.py > nul 2>&1
rd /s /q test > nul 2>&1

:: 2. git add
echo 📝 Git 스테이징...
git add .

:: 3. 커밋 메시지 입력받기
set /p msg=💬 커밋 메시지를 입력하세요: 
git commit -m "%msg%"

:: 4. 푸시
echo ⏫ GitHub로 푸시 중...
git push origin main

echo ✅ 완료! Render에서 자동 배포가 곧 시작돼요!
pause
