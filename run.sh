#!/bin/bash
# 하루 한 번(또는 원하는 주기로) 실행. cron 이나 GitHub Actions 에서 부른다.
cd "$(dirname "$0")" || exit 1
echo "═══ $(date '+%Y-%m-%d %H:%M:%S') 수집 시작 ═══"
python3 build.py; a=$?
python3 news.py;  b=$?
echo "═══ ETF $a · 뉴스 $b ═══"
exit $(( a || b ))
