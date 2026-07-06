# План: OCR таймера обратного отсчёта в попапе «СОВЕТ»

## Проблема
Для рудников 5–6 уровня игра не разрешает отзывать отряд раньше 45 минут. Когда бот пытается отозвать слишком рано, появляется попап «СОВЕТ» с таймером обратного отсчёта (`MM:SS`), показывающим, сколько осталось до разрешённого отзыва.

Сейчас бот просто закрывает попап и синхронизирует таймер приблизительно — считает, что добыча началась с момента закрытия попапа. Это безопасно, но неоптимально: бот ждёт полный `GOLD_MINING_DURATION` заново, хотя реальное оставшееся время может быть меньше.

## Цель
Считывать оставшееся таймер с попапа «СОВЕТ» через OCR и устанавливать `_gold_ctx['started_at']` так, чтобы следующий отзыв произошёл точно по истечении таймера игры.

## Где используется
- `gold.py`, обработчик `GoldState.ADVICE_VISIBLE`.

## Что нужно сделать

### 1. Добавить зависимость OCR
Выбрать легковесное решение для Windows + Python 3.13:
- **Вариант A (рекомендуется):** `pytesseract` + системный `tesseract-ocr`.
- **Вариант B:** `easyocr` — тяжелее, но не требует внешнего бинарника.

Обновить `requirements.txt`:
```
pytesseract>=0.3.13
Pillow>=10.0
```

### 2. Добавить ROI таймера
Определить координаты области с таймером на попапе «СОВЕТ» относительно окна рудника. Сохранить в `config.py`:
```python
GOLD_ADVICE_TIMER_ROI = (x, y, w, h)  # в пикселях относительно окна BlueStacks
```

### 3. Написать OCR-хелпер
Новый файл `ocr_utils.py` или функция в `utils.py`:
```python
def read_advice_timer(screen_cv, region) -> int | None:
    """Возвращает оставшиеся секунды из таймера MM:SS, или None."""
    roi = GOLD_ADVICE_TIMER_ROI
    x = region[0] + roi[0]
    y = region[1] + roi[1]
    w, h = roi[2], roi[3]
    crop = screen_cv[y:y+h, x:x+w]
    # предобработка: grayscale, threshold, resize x2
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    scaled = cv2.resize(binary, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    text = pytesseract.image_to_string(scaled, config='--psm 7 -c tessedit_char_whitelist=0123456789:')
    # парсинг MM:SS
    match = re.match(r'\s*(\d{1,2}):(\d{2})', text)
    if match:
        minutes, seconds = map(int, match.groups())
        return minutes * 60 + seconds
    return None
```

### 4. Интегрировать в `gold.py`
В обработчике `ADVICE_VISIBLE` после нажатия `confirm_orange.png`:
```python
remaining_seconds = read_advice_timer(screen_after, region)
if remaining_seconds is not None:
    # Сдвигаем started_at в прошлое так, что через remaining_seconds recall станет доступен.
    _gold_ctx['started_at'] = time.time() - (GOLD_MINING_DURATION - remaining_seconds)
    update_gold_time()
    logger.info(f"[GOLD] Таймер попапа 'СОВЕТ': {remaining_seconds} сек до отзыва.")
else:
    # Fallback: безопасная синхронизация, как сейчас.
    start_gold_mission()
    update_gold_time()
```

### 5. Тестирование
- Сделать скриншот попапа «СОВЕТ» с разными таймерами.
- Проверить `read_advice_timer` на них через системный Python.
- Убедиться, что fallback срабатывает, если OCR не распознал текст.

## Риски
- OCR может неверно распознать цифры из-за шрифта/тени. Нужен запас в 30–60 сек.
- Установка `tesseract-ocr` на Windows может быть неудобной. Вариант B (`easyocr`) проще в деплое, но тяжелее в runtime.

## Приоритет
Средний. Текущий fallback работает корректно, но OCR позволит сэкономить до 45 минут между циклами золотодобычи.
