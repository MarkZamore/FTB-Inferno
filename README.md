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
