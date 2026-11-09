#!/usr/bin/env bash
# Необязательная консольная оболочка для API Gateway.
# Требования WSL: bash, curl и python3.
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8088}"
API_USERNAME="${API_USERNAME:-teacher}"
API_PASSWORD="${API_PASSWORD:-teacher-secret}"

DEFAULT_TERM="база данных"
DEFAULT_FROM="2026-02-09"
DEFAULT_TO="2026-03-22"
DEFAULT_COURSE_ID="b709955d-7c00-5fe2-85fa-c41f4a375384"
DEFAULT_GROUP_ID="3e1c4997-ed7e-5fe7-97e9-2edd413bea51"

TOKEN=""

read_value() {
    local prompt="$1"
    local default_value="$2"
    local value
    read -r -p "$prompt [$default_value]: " value
    printf '%s' "${value:-$default_value}"
}

read_iso_date() {
    local prompt="$1"
    local default_value="$2"
    local value
    while true; do
        value="$(read_value "$prompt" "$default_value")"
        if [[ "$value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] \
            && python3 -c 'from datetime import date; import sys; date.fromisoformat(sys.argv[1])' "$value" 2>/dev/null; then
            printf '%s' "$value"
            return
        fi
        printf 'Некорректная дата. Используйте существующую дату в формате YYYY-MM-DD.\n' >&2
    done
}

get_token() {
    local response_file status
    response_file="$(mktemp)"
    printf '\nПолучение JWT у %s/auth/token\n' "$API_BASE_URL"

    if ! status="$(curl -sS -o "$response_file" -w '%{http_code}' -X POST \
        "$API_BASE_URL/auth/token?username=$API_USERNAME&password=$API_PASSWORD")"; then
        printf 'Не удалось подключиться к API Gateway: %s\n' "$API_BASE_URL" >&2
        printf 'Сначала запустите: docker compose -f docker-compose.lab.yml up -d --build\n' >&2
        rm -f "$response_file"
        return 1
    fi
    if [[ "$status" != "200" ]]; then
        printf 'JWT не получен: Gateway вернул HTTP %s.\n' "$status" >&2
        cat "$response_file" >&2
        rm -f "$response_file"
        return 1
    fi
    if ! TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' < "$response_file")"; then
        printf 'Gateway вернул некорректный ответ вместо JWT.\n' >&2
        rm -f "$response_file"
        return 1
    fi
    rm -f "$response_file"
    printf 'JWT получен.\n'
}

ensure_token() {
    if [[ -z "$TOKEN" ]]; then
        get_token
    fi
}

show_response() {
    python3 -m json.tool --no-ensure-ascii
}

request_report() {
    local response_file status
    response_file="$(mktemp)"
    if ! status="$(curl -sS -o "$response_file" -w '%{http_code}' "$@")"; then
        printf 'Не удалось подключиться к API Gateway: %s\n' "$API_BASE_URL" >&2
        rm -f "$response_file"
        return 0
    fi
    if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
        printf 'API вернул HTTP %s:\n' "$status" >&2
    fi
    if ! show_response < "$response_file"; then
        cat "$response_file"
    fi
    rm -f "$response_file"
}

run_lab1() {
    local term period_from period_to
    term="$(read_value 'Термин или фраза' "$DEFAULT_TERM")"
    period_from="$(read_iso_date 'Начало периода, YYYY-MM-DD' "$DEFAULT_FROM")"
    period_to="$(read_iso_date 'Конец периода, YYYY-MM-DD' "$DEFAULT_TO")"
    ensure_token
    printf '\nЛР1: поиск 10 студентов с минимальной посещаемостью\n'
    request_report -G "$API_BASE_URL/api/v1/lab1/report" \
        --data-urlencode "term=$term" \
        --data-urlencode "from=$period_from" \
        --data-urlencode "to=$period_to" \
        -H "Authorization: Bearer $TOKEN"
}

run_lab2() {
    local course_id semester year
    course_id="$(read_value 'UUID курса' "$DEFAULT_COURSE_ID")"
    semester="$(read_value 'Семестр' '3')"
    year="$(read_value 'Календарный год занятий' '2026')"
    ensure_token
    printf '\nЛР2: аудитории и технические требования\n'
    request_report -G "$API_BASE_URL/api/v1/lab2/report" \
        --data-urlencode "course_id=$course_id" \
        --data-urlencode "semester=$semester" \
        --data-urlencode "year=$year" \
        -H "Authorization: Bearer $TOKEN"
}

run_lab3() {
    local group_id period_from period_to
    group_id="$(read_value 'UUID группы' "$DEFAULT_GROUP_ID")"
    period_from="$(read_iso_date 'Начало периода, YYYY-MM-DD' "$DEFAULT_FROM")"
    period_to="$(read_iso_date 'Конец периода, YYYY-MM-DD' "$DEFAULT_TO")"
    ensure_token
    printf '\nЛР3: плановые и посещённые часы специальных дисциплин\n'
    request_report -G "$API_BASE_URL/api/v1/lab3/report" \
        --data-urlencode "group_id=$group_id" \
        --data-urlencode "from=$period_from" \
        --data-urlencode "to=$period_to" \
        -H "Authorization: Bearer $TOKEN"
}

show_menu() {
    cat <<'MENU'

University API console
1 — получить JWT
2 — отчёт ЛР1
3 — отчёт ЛР2
4 — отчёт ЛР3
5 — последовательно выполнить все отчёты
0 — выход
MENU
}

run_choice() {
    local choice="$1"
    case "$choice" in
        token|1) get_token ;;
        lab1|2) run_lab1 ;;
        lab2|3) run_lab2 ;;
        lab3|4) run_lab3 ;;
        all|5) run_lab1; run_lab2; run_lab3 ;;
        0|exit) ;;
        *)
            printf 'Неизвестное действие: %s\n' "$choice" >&2
            printf 'Используйте: token, lab1, lab2, lab3 или all.\n' >&2
            return 2
            ;;
    esac
}

main() {
    # Явный аргумент сохраняет неинтерактивный режим: ./api_console.sh lab1.
    if [[ $# -gt 0 ]]; then
        run_choice "$1"
        return
    fi

    # Интерактивный режим не завершается после запроса: JWT остаётся в TOKEN.
    while true; do
        local choice
        show_menu
        read -r -p 'Выберите действие: ' choice
        case "$choice" in
            0|exit)
                printf 'Работа завершена.\n'
                break
                ;;
            *)
                run_choice "$choice" || printf 'Действие не выполнено; консоль остаётся открытой.\n' >&2
                ;;
        esac
    done
}

main "$@"
