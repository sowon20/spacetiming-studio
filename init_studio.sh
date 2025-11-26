#!/bin/bash

echo "📁 시공간 스튜디오 기본 폴더 생성 중..."

# Create base folders
mkdir -p veo_agent
mkdir -p telegram_bot
mkdir -p flow_automation
mkdir -p sidebar_extension
mkdir -p studio_dashboard

echo "📝 README 파일 생성..."

echo "# Veo Agent" > veo_agent/README.md
echo "# Telegram Bot" > telegram_bot/README.md
echo "# Flow Automation" > flow_automation/README.md
echo "# Sidebar Extension" > sidebar_extension/README.md
echo "# Studio Dashboard" > studio_dashboard/README.md

echo "✨ 기본 구조 생성 완료!"