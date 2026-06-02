"""
exporters/fields_node.py
========================
Итерация 2.1 — разбор полей каждой ноды.

Для каждого узла строятся два объекта:

  table_alias_map[node_id] — список записей
    {
      "alias":         str,   # псевдоним таблицы (как он стоит в FROM/JOIN)
      "primary_table": str,   # первичная таблица (из AS / КАК, или == alias)
      "is_virtual":    bool,  # True  → ВТ (есть в node_names)
                              # False → физическая таблица 1С (терминал)
      "join_type":     str,  # "ИЗ", "ЛЕВОЕ_СОЕДИНЕНИЕ", "ВНУТРЕННЕЕ_СОЕДИНЕНИЕ" и т.д.
    }

  fields_node[node_id] — список записей
    {
      "alias":         str,   # синоним поля (после КАК / AS) или pseudo-alias
      "expression_raw":str,   # выражение как есть из SELECT / WHERE / JOIN ON
      "expr_type":     str,   # тип: см. EXPR_TYPES ниже
      "field_refs":    list   # все пары {alias_table, field, primary_table}
    }

  field_refs[]
    {
      "alias_table":   str,   # псевдоним таблицы из выражения (напр. "д")
      "field":         str,   # имя поля (может быть "Контрагент.Наименование")
      "primary_table": str    # первичная таблица из table_alias_map
    }

Типы expr_type
--------------
  field_ref         — простая ссылка: Таблица.Поле
  case_when         — ВЫБОР КОГДА ... КОНЕЦ
  func_call         — функция: ДОБАВИТЬКДАТЕ(...), СУММА(...) и др.
  aggregate         — агрегат без аргумента-поля: КОЛИЧЕСТВО(*)
  arithmetic        — арифметическое выражение: А * Б + В
  literal           — строка, число, NULL, &Параметр, ЗНАЧЕНИЕ(...)
  star              — * (все поля)
  where_condition   — условие ГДЕ/WHERE (pseudo-field alias = "ГДЕ_УСЛОВИЕ")
  join_on_condition — условие ПО/ON в JOIN (pseudo-field alias = "ТИП_СОЕДИНЕНИЯ_<alias>_УСЛОВИЕ")
  join_table        — таблица в JOIN (pseudo-field alias = "ТИП_СОЕДИНЕНИЯ_<alias>")

Правило трассировки (используется в exporters/lineage.py):
  - field_ref с is_virtual=True → рекурсия в source_node
  - field_ref с is_virtual=False → СТОП, физическая таблица
  - literal / star → СТОП, нет данных для трассировки
  - case_when / func_call / arithmetic → рекурсия по всем field_refs
  - where_condition / join_on_condition → рекурсия по field_refs (условия содержат ссылки)
  - join_table → СТОП, это терминальная таблица
"""

import re
from typing import Optional

# ──────────────────────────────────────────────
# Константы
# ──────────────────────────────────────────────

EXPR_TYPES = (
    "field_ref", "case_when", "func_call", "aggregate",
    "arithmetic", "literal", "star",
    "where_condition", "join_on_condition", "join_table",
)

# Ключевые слова 1С/SQL, не являющиеся именами таблиц или полей
_KW = re.compile(
    r'^(?:NULL|ИСТИНА|ЛОЖЬ|TRUE|FALSE|ЗНАЧЕНИЕ|ДОБАВИТЬКДАТЕ|DATEADD'
    r'|НАЧАЛОПЕРИОДА|КОНЕЦПЕРИОДА|НАЧАЛОСТАНДАРТНОГОИНТЕРВАЛА'
    r'|ГОД|КВАРТАЛ|МЕСЯЦ|НЕДЕЛЯ|ДЕНЬ|ЧАС|МИНУТА|СЕКУНДА'
    r'|YEAR|QUARTER|MONTH|WEEK|DAY|HOUR|MINUTE|SECOND'
    r'|ISNULL|ЕСТЬNULL|ПРЕДСТАВЛЕНИЕ|ТИПЗНАЧЕНИЯ|ССЫЛКА'
    r'|СУММА|МИНИМУМ|МАКСИМУМ|СРЕДНЕЕ|КОЛИЧЕСТВО'
    r'|SUM|MIN|MAX|AVG|COUNT)$',
    re.IGNORECASE,
)

# Агрегатные функции
_AGGREGATE_FUNCS = re.compile(
    r'^(?:СУММА|МИНИМУМ|МАКСИМУМ|СРЕДНЕЕ|КОЛИЧЕСТВО|SUM|MIN|MAX|AVG|COUNT)$',
    re.IGNORECASE,
)

# Функции (не агрегаты)
_FUNC_FUNCS = re.compile(
    r'^(?:ДОБАВИТЬКДАТЕ|DATEADD|НАЧАЛОПЕРИОДА|КОНЕЦПЕРИОДА'
    r'|НАЧАЛОСТАНДАРТНОГОИНТЕРВАЛА|ЕСТЬNULL|ISNULL'
    r'|ПРЕДСТАВЛЕНИЕ|ТИПЗНАЧЕНИЯ|ПОДСТРОКА|SUBSTRING'
    r'|ДЛИНА|LEN|СТРНАЙТИ|STRPOS|ВЫРАЗИТЬ|CAST'
    r'|ГОД|КВАРТАЛ|МЕСЯЦ|НЕДЕЛЯ|ДЕНЬ|ЧАС|МИНУТА|СЕКУНДА'
    r'|YEAR|QUARTER|MONTH|WEEK|DAY|HOUR|MINUTE|SECOND)$',
    re.IGNORECASE,
)


# ──────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────

def _hide_strings(text: str) -> tuple:
    """
    Скрывает строковые литералы ("...") и ЗНАЧЕНИЕ(...) чтобы не парсить их содержимое.
    Возвращает (обработанный текст, словарь замен).
    """
    placeholders = {}
    counter = [0]

    def _replace(m):
        key = f"__STR{counter[0]}__"
        counter[0] += 1
        placeholders[key] = m.group(0)
        return key

    # Сначала ЗНАЧЕНИЕ(...) — вложенных скобок нет
    result = re.sub(r'ЗНАЧЕНИЕ\s*\([^)]*\)', _replace, text, flags=re.IGNORECASE)
    # Затем строковые литералы
    result = re.sub(r'"[^"]*"', _replace, result)
    result = re.sub(r"'[^']*'", _replace, result)
    return result, placeholders


def _restore_strings(text: str, placeholders: dict) -> str:
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


def _remove_nested_parens(text: str) -> str:
    """Рекурсивно убирает () → пробел (нейтрализует вложенные выражения)."""
    while True:
        new = re.sub(r'\([^()]*\)', ' ', text)
        if new == text:
            break
        text = new
    return text


def _split_select_list(text: str) -> list:
    """
    Разбивает SELECT-список на отдельные выражения по запятой верхнего уровня.
    Вложенные скобки (подзапросы, функции) обходятся корректно.
    """
    items = []
    depth = 0
    current = []
    for ch in text:
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            items.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        items.append(''.join(current).strip())
    return [i for i in items if i]


def _extract_select_block(node_text: str) -> Optional[str]:
    """
    Вырезает содержимое между ВЫБРАТЬ/SELECT и следующим ключевым словом
    (ИЗ/FROM/ГДЕ/WHERE/СГРУППИРОВАТЬ/GROUP/УПОРЯДОЧИТЬ/ORDER/ИТОГИ/HAVING/...)
    Возвращает строку со списком полей или None если ВЫБРАТЬ не найден.
    """
    blocks = _extract_all_select_blocks(node_text, limit=1)
    return blocks[0] if blocks else None


def _extract_all_select_blocks(node_text: str, limit: int = 0) -> list:
    """
    Извлекает ВСЕ SELECT-блоки из текста, включая части UNION.

    Параметр limit: максимальное количество блоков (0 = без ограничения).
    Возвращает список строк — содержимое SELECT-списков.
    """
    # Скрываем строковые литералы, чтобы не путать ВЫБРАТЬ внутри строк
    safe, ph = _hide_strings(node_text)

    # Находим все ВЫБРАТЬ/SELECT на верхнем уровне (вне скобок)
    select_positions = []
    for m in re.finditer(
        r'(?:^|\s)(?:ВЫБРАТЬ|SELECT)(?:\s+(?:ПЕРВЫЕ|TOP)\s+\d+)?(?:\s+(?:РАЗЛИЧНЫЕ|DISTINCT))?\s',
        safe, re.IGNORECASE,
    ):
        pos = m.start()
        depth = 0
        for ch in safe[:pos]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth == 0:
            select_positions.append(pos)
        if limit and len(select_positions) >= limit:
            break

    if not select_positions:
        return []

    # Для каждой позиции ВЫБРАТЬ извлекаем блок до следующего ВЫБРАТЬ или конца safe
    blocks = []
    for i, start in enumerate(select_positions):
        end = select_positions[i + 1] if i + 1 < len(select_positions) else len(safe)
        part = safe[start:end]
        # Используем _extract_select_block_raw — тот же алгоритм, но без поиска ВЫБРАТЬ
        block = _extract_select_block_raw(part)
        if block:
            blocks.append(_restore_strings(block, ph))

    return blocks


def _extract_select_block_raw(rest: str) -> Optional[str]:
    """
    Вырезает содержимое SELECT-списка из строки, которая уже начинается с ВЫБРАТЬ.
    Аналог _extract_select_block, но без поиска самого ВЫБРАТЬ.
    """
    # Пропускаем ВЫБРАТЬ ... до первого пробела после ключевого слова
    m = re.match(
        r'(?:^|\s)(?:ВЫБРАТЬ|SELECT)(?:\s+(?:ПЕРВЫЕ|TOP)\s+\d+)?(?:\s+(?:РАЗЛИЧНЫЕ|DISTINCT))?\s',
        rest, re.IGNORECASE,
    )
    if not m:
        return None

    start = m.end()
    rest = rest[start:]

    stop_pattern = re.compile(
        r'(?:^|\s)(?:ИЗ|FROM|ГДЕ|WHERE|СГРУППИРОВАТЬ|GROUP\s+BY'
        r'|УПОРЯДОЧИТЬ|ORDER\s+BY|ИТОГИ|TOTALS|ИМЕЮЩИЕ|HAVING'
        r'|ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE|ПОМЕСТИТЬ|INTO)(?:\s|$)',
        re.IGNORECASE,
    )

    depth = 0
    i = 0
    end = len(rest)
    while i < len(rest):
        ch = rest[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            tail = rest[i:]
            if stop_pattern.match(tail) or stop_pattern.search(' ' + tail[:10]):
                m2 = stop_pattern.search(rest[i - 1:] if i > 0 else rest)
                if m2 and depth == 0:
                    sm = re.search(
                        r'(?:^|(?<=\s))(?:ИЗ|FROM|ГДЕ|WHERE'
                        r'|СГРУППИРОВАТЬ|GROUP\s+BY'
                        r'|УПОРЯДОЧИТЬ|ORDER\s+BY'
                        r'|ИТОГИ|TOTALS|ИМЕЮЩИЕ|HAVING'
                        r'|ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE|ПОМЕСТИТЬ|INTO)(?=\s|$)',
                        rest[i:], re.IGNORECASE,
                    )
                    if sm:
                        end = i + sm.start()
                        break
        i += 1

    return rest[:end].strip()


# ──────────────────────────────────────────────
# Парсер WHERE / JOIN ON
# ──────────────────────────────────────────────

_WHERE_STOP_RE = re.compile(
    r'(?:^|\s)(?:СГРУППИРОВАТЬ|GROUP\s+BY|УПОРЯДОЧИТЬ|ORDER\s+BY'
    r'|ИТОГИ|TOTALS|ИМЕЮЩИЕ|HAVING|ОБЪЕДИНИТЬ|UNION'
    r'|ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE)(?:\s|$)',
    re.IGNORECASE,
)

_JOIN_ON_STOP_RE = re.compile(
    r'(?:^|\s)(?:СОЕДИНЕНИЕ|JOIN|ГДЕ|WHERE'
    r'|СГРУППИРОВАТЬ|GROUP\s+BY|УПОРЯДОЧИТЬ|ORDER\s+BY'
    r'|ИТОГИ|TOTALS|ИМЕЮЩИЕ|HAVING|ОБЪЕДИНИТЬ|UNION'
    r'|ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE)(?:\s|$)',
    re.IGNORECASE,
)


def _extract_where_block(node_text: str) -> Optional[str]:
    """
    Извлекает условие из блока ГДЕ/WHERE.
    Возвращает текст условия (без ключевого слова ГДЕ) или None.
    """
    safe, ph = _hide_strings(node_text)

    keyword_re = re.compile(r'(?:^|\s)(?:ГДЕ|WHERE)\s', re.IGNORECASE)
    m = keyword_re.search(safe)
    if not m:
        return None

    start = m.end()
    rest = safe[start:]

    depth = 0
    i = 0
    end = len(rest)
    while i < len(rest):
        ch = rest[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            tail = rest[i:]
            if _WHERE_STOP_RE.match(tail) or _WHERE_STOP_RE.search(' ' + tail[:10]):
                m2 = _WHERE_STOP_RE.search(rest[i - 1:] if i > 0 else rest)
                if m2 and depth == 0:
                    sm = re.search(
                        r'(?:^|(?<=\s))(?:СГРУППИРОВАТЬ|GROUP\s+BY|УПОРЯДОЧИТЬ|ORDER\s+BY'
                        r'|ИТОГИ|TOTALS|ИМЕЮЩИЕ|HAVING|ОБЪЕДИНИТЬ|UNION'
                        r'|ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE)(?=\s|$)',
                        rest[i:], re.IGNORECASE,
                    )
                    if sm:
                        end = i + sm.start()
                        break
        i += 1

    return _restore_strings(rest[:end].strip(), ph)


def _extract_join_on_conditions(node_text: str) -> list:
    """
    Извлекает все условия ПО/ON для JOIN'ов в ноде.
    Возвращает список словарей:
        [{"condition_text": "..."}, ...]
    Порядок условий соответствует порядку JOIN'ов в тексте.
    """
    safe, ph = _hide_strings(node_text)

    on_pattern = re.compile(r'(?:^|\s)(?:ПО|ON)\s', re.IGNORECASE)
    conditions = []

    for m in on_pattern.finditer(safe):
        pos = m.start()
        # Проверяем, что мы на верхнем уровне (вне скобок подзапросов)
        depth = 0
        for ch in safe[:pos]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth != 0:
            continue

        start = m.end()
        rest = safe[start:]

        depth2 = 0
        i = 0
        end = len(rest)
        while i < len(rest):
            ch = rest[i]
            if ch == '(':
                depth2 += 1
            elif ch == ')':
                depth2 -= 1
            elif depth2 == 0:
                tail = rest[i:]
                if _JOIN_ON_STOP_RE.match(tail) or _JOIN_ON_STOP_RE.search(' ' + tail[:10]):
                    m2 = _JOIN_ON_STOP_RE.search(rest[i - 1:] if i > 0 else rest)
                    if m2 and depth2 == 0:
                        sm = re.search(
                            r'(?:^|(?<=\s))(?:СОЕДИНЕНИЕ|JOIN|ГДЕ|WHERE'
                            r'|СГРУППИРОВАТЬ|GROUP\s+BY|УПОРЯДОЧИТЬ|ORDER\s+BY'
                            r'|ИТОГИ|TOTALS|ИМЕЮЩИЕ|HAVING|ОБЪЕДИНИТЬ|UNION'
                            r'|ДЛЯ ИЗМЕНЕНИЯ|FOR UPDATE)(?=\s|$)',
                            rest[i:], re.IGNORECASE,
                        )
                        if sm:
                            end = i + sm.start()
                            break
            i += 1

        condition_text = _restore_strings(rest[:end].strip(), ph)
        conditions.append({"condition_text": condition_text})

    return conditions


# ──────────────────────────────────────────────
# Парсер alias-map (FROM / JOIN блок)
# ──────────────────────────────────────────────

def parse_table_alias_map(node_text: str, virtual_table_names: set) -> list:
    """
    Разбирает FROM/JOIN-блок ноды и возвращает table_alias_map:

    [
      {
        "alias":         str,   # псевдоним как он используется в выражениях
        "primary_table": str,   # реальное имя таблицы (из КАК/AS или == alias)
        "is_virtual":    bool   # входит ли в множество virtual_table_names
      },
      ...
    ]

    Примеры:
      ИЗ Справочник.Договоры КАК д  →  alias="д", primary="Справочник.Договоры"
      ИЗ ВТ_Остатки                  →  alias="ВТ_Остатки", primary="ВТ_Остатки"
      ЛЕВОЕ СОЕДИНЕНИЕ Рег.Ост КАК о →  alias="о", primary="Рег.Ост"

    ВОЗМОЖНАЯ ОШИБКА:
      Если подзапрос в FROM имеет псевдоним, его содержимое уже схлопнуто
      в «~id~» парсером sql_query_analyzer. Такие записи помечаются
      is_virtual=True и в primary_table ставится сам псевдоним.
    """
    text, ph = _hide_strings(node_text)

    # Убираем содержимое подзапросов — они уже разобраны как дочерние ноды
    # Схлопываем скобки рекурсивно
    flat = _remove_nested_parens(text)

    # Обрезаем всё до первого ИЗ/FROM — иначе запятые из SELECT-списка
    # будут ошибочно распознаны как разделители таблиц
    from_m = re.search(r'(?:^|\s)(?:ИЗ|FROM)\s', flat, re.IGNORECASE)
    if from_m:
        flat = flat[from_m.start():]
    else:
        return []

    # Паттерн: (ИЗ|FROM|JOIN|СОЕДИНЕНИЕ) <таблица> [КАК <псевдоним>]
    pattern = re.compile(
        r'(?:(ИЗ|FROM)'
        r'|((?:ЛЕВОЕ|ПРАВОЕ|ПОЛНОЕ|ВНУТРЕННЕЕ|CROSS|LEFT|RIGHT|FULL|INNER|OUTER)?'
        r'\s*(?:СОЕДИНЕНИЕ|JOIN))'
        r'|,)'
        r'\s+([\w.~]+)'
        r'(?:\s+(?:КАК|AS)\s+([\w]+))?',
        re.IGNORECASE,
    )

    result = []
    seen_aliases = set()

    for m in pattern.finditer(flat):
        join_type_raw = m.group(1) or m.group(2)
        primary = m.group(3).strip()
        alias = m.group(4).strip() if m.group(4) else primary

        # Восстанавливаем строки в именах (маловероятно, но на всякий случай)
        primary = _restore_strings(primary, ph)
        alias = _restore_strings(alias, ph)

        alias_upper = alias.upper()
        if alias_upper in seen_aliases:
            continue
        seen_aliases.add(alias_upper)

        is_virtual = primary.upper() in virtual_table_names

        # Нормализуем join_type: "ИЗ" → "ИЗ", "ЛЕВОЕ СОЕДИНЕНИЕ" → "ЛЕВОЕ_СОЕДИНЕНИЕ"
        if join_type_raw:
            join_type = join_type_raw.strip().upper().replace(' ', '_')
        else:
            join_type = 'FROM'  # запятая — считаем продолжением FROM

        result.append({
            "alias": alias,
            "primary_table": primary,
            "is_virtual": is_virtual,
            "join_type": join_type,
        })

    return result


# ──────────────────────────────────────────────
# Парсер полей (SELECT-список)
# ──────────────────────────────────────────────

def _classify_expr(expr: str) -> str:
    """
    Определяет тип выражения по его тексту (верхний уровень).

    ВОЗМОЖНАЯ ОШИБКА:
      Арифметика вида «А + Б» при наличии пробелов может быть
      распознана как field_ref если регекс не найдёт оператор.
      Критичных случаев пока нет, но при появлении — расширить
      паттерн _ARITH_OPS.
    """
    e = expr.strip()
    if not e:
        return "literal"

    el = e.upper()

    if el == '*':
        return "star"

    # ВЫБОР / CASE
    if re.match(r'^(?:ВЫБОР|CASE)\b', e, re.IGNORECASE):
        return "case_when"

    # Параметр &Х или строковый литерал или ЗНАЧЕНИЕ(...) или число
    if re.match(r'^(?:&|__STR\d+__|\d|"|\')', e):
        return "literal"
    if re.match(r'^(?:NULL|ИСТИНА|ЛОЖЬ|TRUE|FALSE)$', e, re.IGNORECASE):
        return "literal"

    # Функция: ИМЯ(
    func_m = re.match(r'^([\w]+)\s*\(', e, re.IGNORECASE)
    if func_m:
        func_name = func_m.group(1).upper()
        if _AGGREGATE_FUNCS.match(func_name):
            return "aggregate"
        return "func_call"

    # Арифметика: содержит +, -, *, /
    flat = _remove_nested_parens(e)
    if re.search(r'[+\-*/]', flat):
        return "arithmetic"

    # Простая ссылка: Таблица.Поле или просто Поле
    return "field_ref"


def _extract_field_refs(expr: str, alias_map: list) -> list:
    """
    Извлекает все ссылки вида <ПсевдонимТаблицы>.<Поле> из выражения.

    Возвращает список:
    [
      {
        "alias_table":   str,
        "field":         str,
        "primary_table": str   # из alias_map, или == alias_table если не найден
      }
    ]

    ВОЗМОЖНАЯ ОШИБКА:
      Если псевдоним таблицы не найден в alias_map текущей ноды,
      primary_table = alias_table (не резолвится). Это происходит
      когда ссылка идёт на поле из родительской ноды или когда
      alias_map неполный из-за сложного синтаксиса СОЕДИНЕНИЯ.
    """
    # Строим быстрый lookup alias → primary_table
    lookup = {}
    for entry in alias_map:
        lookup[entry["alias"].upper()] = entry

    text, ph = _hide_strings(expr)

    # Ищем все «слово.слово» (возможно цепочка: А.Б.В)
    refs_raw = re.findall(r'([\w]+)\.([\w.]+)', text)

    result = []
    seen = set()

    for alias_table, field in refs_raw:
        # Пропускаем ЗНАЧЕНИЕ(Перечисление.Х.У) — уже скрыто в ph
        if _KW.match(alias_table):
            continue
        if alias_table.startswith('__STR'):
            continue

        key = (alias_table.upper(), field.upper())
        if key in seen:
            continue
        seen.add(key)

        entry = lookup.get(alias_table.upper())
        primary = entry["primary_table"] if entry else alias_table

        result.append({
            "alias_table": alias_table,
            "field": field,
            "primary_table": primary,
        })

    return result


def _parse_alias_from_expr(expr: str) -> tuple:
    """
    Выделяет (выражение_без_алиаса, алиас) из элемента SELECT-списка.

    Примеры:
      "д.Ссылка КАК Договор"       → ("д.Ссылка", "Договор")
      "СУММА(X.Сумма) AS Итого"    → ("СУММА(X.Сумма)", "Итого")
      "д.Ссылка"                   → ("д.Ссылка", "Ссылка")  ← fallback
      "*"                           → ("*", "*")

    ВОЗМОЖНАЯ ОШИБКА:
      Если алиаса нет и выражение сложное (CASE/функция),
      fallback-алиас будет пустой строкой или некорректным.
      В таких случаях рекомендуется явно задавать КАК.
    """
    # Паттерн: ... КАК <алиас> в конце (не внутри скобок)
    # Ищем КАК/AS вне скобок
    depth = 0
    last_as_pos = -1
    i = 0
    tokens = re.split(r'(\s+)', expr)  # сохраняем пробелы
    flat_tokens = []
    for tok in tokens:
        flat_tokens.append(tok)

    # Более надёжный подход: ищем \bКАК\b или \bAS\b на верхнем уровне вложенности
    depth = 0
    pos = 0
    as_start = -1
    as_end = -1

    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            # Проверяем КАК или AS
            tail = expr[i:]
            m = re.match(r'^(?:КАК|AS)\s+(\w+)\s*$', tail, re.IGNORECASE)
            if m:
                as_start = i
                as_end = i + len(tail)
                break
        i += 1

    if as_start >= 0:
        alias = expr[as_start:].strip()
        alias = re.sub(r'^(?:КАК|AS)\s+', '', alias, flags=re.IGNORECASE).strip()
        expression = expr[:as_start].strip()
    else:
        expression = expr.strip()
        # Fallback алиас: последний токен после последней точки
        m = re.search(r'\.([\w]+)\s*$', expression)
        alias = m.group(1) if m else expression.split()[-1] if expression else ""

    return expression, alias


# ──────────────────────────────────────────────
# Главная функция
# ──────────────────────────────────────────────

def build_fields_and_alias_map(nodes: list) -> dict:
    """
    Принимает список нод (из analyze_sql_query → result["nodes"]).
    Возвращает:
    {
      "fields_node":      { node_id(str): [ field_record, ... ] },
      "table_alias_map":  { node_id(str): [ alias_record,  ... ] }
    }

    field_record:
    {
      "alias":         str,
      "expression_raw":str,
      "expr_type":     str,
      "field_refs":    [ {alias_table, field, primary_table}, ... ]
    }

    Обрабатываются ноды всех типов (temp_query, result, sub_query).
    Ноды типа sub_query без SELECT-блока пропускаются без ошибки.

    Для нод с ОБЪЕДИНИТЬ/UNION:
      - alias'ы берутся из первой части
      - field_refs объединяются из всех частей (дедупликация по alias_table+field)
      - expr_type берётся из первой части
    """
    # Множество имён виртуальных таблиц (все temp_query) для is_virtual
    virtual_names = {
        n["name"].upper()
        for n in nodes
        if n["type"] == "temp_query"
    }

    fields_node = {}
    table_alias_map = {}

    for node in nodes:
        nid = str(node["id"])
        node_text = node.get("text", "")

        # ── 1. table_alias_map ──────────────────
        alias_map = parse_table_alias_map(node_text, virtual_names)
        table_alias_map[nid] = alias_map

        # ── 2. fields_node ──────────────────────
        select_blocks = _extract_all_select_blocks(node_text)
        if not select_blocks:
            fields_node[nid] = []
            continue

        # Первая часть — основная (alias'ы и expr_type отсюда)
        first_items = _split_select_list(select_blocks[0])
        field_records = []

        for idx, item in enumerate(first_items):
            item = item.strip()
            if not item:
                continue

            expression, alias = _parse_alias_from_expr(item)
            expr_type = _classify_expr(expression)
            refs = _extract_field_refs(expression, alias_map)

            # Объединяем field_refs из всех частей UNION
            all_refs = list(refs)
            seen_refs = {(r["alias_table"].upper(), r["field"].upper()) for r in refs}

            for block in select_blocks[1:]:
                items = _split_select_list(block)
                if idx < len(items):
                    other_expr, _ = _parse_alias_from_expr(items[idx].strip())
                    other_refs = _extract_field_refs(other_expr, alias_map)
                    for r in other_refs:
                        key = (r["alias_table"].upper(), r["field"].upper())
                        if key not in seen_refs:
                            seen_refs.add(key)
                            all_refs.append(r)

            field_records.append({
                "alias": alias,
                "expression_raw": expression,
                "expr_type": expr_type,
                "field_refs": all_refs,
            })

        # ── 3. WHERE pseudo-field ─────────────────
        where_expr = _extract_where_block(node_text)
        if where_expr:
            where_refs = _extract_field_refs(where_expr, alias_map)
            field_records.append({
                "alias": "ГДЕ_УСЛОВИЕ",
                "expression_raw": where_expr,
                "expr_type": "where_condition",
                "field_refs": where_refs,
            })

        # ── 4. JOIN pseudo-fields ─────────────────
        # Таблицы в alias_map: [0] — FROM, [1:] — JOIN
        on_conditions = _extract_join_on_conditions(node_text)
        for idx, entry in enumerate(alias_map[1:], start=0):
            join_type = entry.get("join_type", "JOIN")
            alias = entry["alias"]
            primary = entry["primary_table"]

            # JOIN table pseudo-field
            field_records.append({
                "alias": f"{join_type}_{alias}",
                "expression_raw": primary,
                "expr_type": "join_table",
                "field_refs": [],
            })

            # JOIN ON condition pseudo-field
            if idx < len(on_conditions):
                on_expr = on_conditions[idx]["condition_text"]
                on_refs = _extract_field_refs(on_expr, alias_map)
                field_records.append({
                    "alias": f"{join_type}_{alias}_УСЛОВИЕ",
                    "expression_raw": f"ПО {on_expr}",
                    "expr_type": "join_on_condition",
                    "field_refs": on_refs,
                })

        fields_node[nid] = field_records

    return {
        "fields_node": fields_node,
        "table_alias_map": table_alias_map,
    }


# ──────────────────────────────────────────────
# Экспортёр файлов
# ──────────────────────────────────────────────

def generate_fields_node(model: dict, output_dir: str) -> None:
    """
    Генерирует файлы итерации 2.1 (fields_node + table_alias_map) в output_dir.

    Создаёт:
      fields_node/fields_node.json
      fields_node/table_alias_map.json
      fields_node/fields_node.csv
      fields_node/table_alias_map.csv
    """
    import csv
    import json
    import os

    result = build_fields_and_alias_map(model["nodes"])

    out_dir = os.path.join(output_dir, "fields_node")
    os.makedirs(out_dir, exist_ok=True)

    # JSON
    with open(os.path.join(out_dir, "fields_node.json"), "w", encoding="utf-8") as f:
        json.dump(result["fields_node"], f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "table_alias_map.json"), "w", encoding="utf-8") as f:
        json.dump(result["table_alias_map"], f, ensure_ascii=False, indent=2)

    # CSV: fields_node — разворачиваем field_refs
    fn_rows = []
    for nid, records in result["fields_node"].items():
        for rec in records:
            base = {
                "node_id": nid,
                "alias": rec["alias"],
                "expression_raw": rec["expression_raw"],
                "expr_type": rec["expr_type"],
            }
            if rec["field_refs"]:
                for ref in rec["field_refs"]:
                    fn_rows.append({
                        **base,
                        "alias_table": ref["alias_table"],
                        "field": ref["field"],
                        "primary_table": ref["primary_table"],
                    })
            else:
                fn_rows.append({
                    **base,
                    "alias_table": "",
                    "field": "",
                    "primary_table": "",
                })

    with open(os.path.join(out_dir, "fields_node.csv"), "w", newline="", encoding="utf-8") as f:
        if fn_rows:
            writer = csv.DictWriter(f, fieldnames=list(fn_rows[0].keys()))
            writer.writeheader()
            writer.writerows(fn_rows)

    # CSV: table_alias_map
    am_rows = []
    for nid, entries in result["table_alias_map"].items():
        for e in entries:
            am_rows.append({
                "node_id": nid,
                "alias": e["alias"],
                "primary_table": e["primary_table"],
                "is_virtual": "1" if e["is_virtual"] else "0",
                "join_type": e.get("join_type", ""),
            })

    with open(os.path.join(out_dir, "table_alias_map.csv"), "w", newline="", encoding="utf-8") as f:
        if am_rows:
            writer = csv.DictWriter(f, fieldnames=list(am_rows[0].keys()))
            writer.writeheader()
            writer.writerows(am_rows)
