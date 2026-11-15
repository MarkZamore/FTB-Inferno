# FTB Inferno

Подготовка сборки 1.12.0 для LANMinecraft. [Авторский клиентский выпуск](https://www.curseforge.com/minecraft/modpacks/ftb-inferno/files/8084377)

`tools/upstream-client-lock.json` фиксирует SHA256 и размер оригинального ZIP, ссылки на официальный источник, записи зависимостей и SHA256 файлов внутри авторских overrides. Minecraft и загрузчик взяты из оригинального манифеста. Java в `portable-pack.json` соответствует выбору текущего лаунчера для этой версии Minecraft и проверяется при запуске.

## Восстановление авторского клиента

Закреплённый авторский клиент CurseForge использует project ID 1091248 и file ID 8084377.
Для подготовки текущего кандидата из корня LANMinecraft запустите:

```powershell
python -B tools/PackData/CurseForge/release_overlay.py stage --pack-source LocalSources/FTB-Inferno --output $stage
```

`tools/overlay.json` сохраняет политику открытия мира через Steam. Для нового авторского выпуска снимите отдельную квитанцию через `prepare.py --client-only` и проверьте её командой `release_overlay.py review-update`. При изменении защищённого входа пересмотрите рецепт и закрепите новые точные байты. После нативной проверки сохраните полный `tools/upstream-lock.json` и выполните `release_overlay.py verify` по готовому манифесту.

## Шейдеры

Euphoria Patcher 1.8.6 ищет Complementary Shaders r5.7.1. Для локальной проверки положите оригинальные ZIP-архивы в папку `shaderpacks` игрового экземпляра. Патчер создаёт свой вариант при запуске. [Reimagined r5.7.1](https://modrinth.com/shader/complementary-reimagined/version/836bPNGo) · [Unbound r5.7.1](https://modrinth.com/shader/complementary-unbound/version/d8rcvDTp)

ZIP для выпуска берутся из оригинальных загрузок и сверяются со списком `tools/shaders-lock.json`. Архивы доступны как часть FTB Inferno в GitHub Releases по разрешению, подтверждённому владельцем сборки. Git хранит ссылки и контрольные суммы. Отдельно сгенерированные варианты Euphoria Patches создаёт игра при первом запуске.

## Публикация

Условия FTB предоставляют право личного использования. Полная перепубликация требует разрешения FTB и владельцев ограниченных зависимостей. [Условия](https://www.feed-the-beast.com/policies/modpacks-mods-policy)

Пользователь подтвердил наличие разрешения на перезалив. Публикация следует после проверки полного состава и нативной приёмки.

## Русский квестбук

Квестбук выбирает язык по настройке Minecraft. Для русского варианта выберите «Русский» в меню языка. Слой включает названия, подзаголовки и описания квестов, названия глав, групп и таблиц наград. Английские строки сохраняются в `en_us`, русский текст в `ru_ru`. Авторские ID, зависимости, условия, команды, предметы и награды остаются прежними.

Ручной перевод хранится в `tools/questbook/ru`. Генератор принимает каталог с **исходными** SNBT из закреплённого авторского ZIP:

```powershell
python -B LocalSources/FTB-Inferno/tools/questbook/build.py extract $authorGame --output $strings
python -B LocalSources/FTB-Inferno/tools/questbook/build.py write $authorGame
python -B LocalSources/FTB-Inferno/tools/questbook/build.py verify $authorGame
```

При обновлении автора сначала сравните новый клиентский lock с текущим:

```powershell
python -B LocalSources/FTB-Inferno/tools/questbook/build.py review-update $candidateLock --release-overlay tools/PackData/CurseForge/release_overlay.py
```

Если SNBT и версии FTB Quests, FTB Library и KubeJS совпали, проверка переносит привязку overlay на новый архив. Сохраните предложенный рецепт вместе с обновлёнными locks и прогоните штатные `stage --locked` и `verify`. Если автор изменил, добавил или удалил файл квестбука, проверка перечислит эти пути. Сначала сверьте изменения по ID квестов и обновите соответствующие словари, затем пересоберите overlay на проверенных исходных байтах. Проверка покрытия требует перевода каждой новой отображаемой строки.

Для выпуска одного квестбука поверх существующего проверенного релиза используйте `tools/questbook/stage_release.py $output --base $publishedRevision`. Скрипт сверяет точную ревизию, заменяет только архивы затронутых файлов, добавляет языки и обновляет карточку. При полном авторском обновлении сохраняйте также оба шейдерпака из `tools/shaders-lock.json`.

## Пресет управления

Раскладка поставляется в `launcher/controls-preset.txt`. Редактирование, проверка и повторная публикация после авторского обновления описаны в [инструкции пресета](tools/keybinds/design.md).
