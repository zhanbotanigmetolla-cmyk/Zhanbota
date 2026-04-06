@echo off
git push origin main
ssh nigmetolla_zhanbota@34.123.71.99 "bash ~/deploy.sh"
echo Done!
pause