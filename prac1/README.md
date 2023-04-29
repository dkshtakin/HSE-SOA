# Практика 1. Docker. Сокеты. Сериализация и десериализация данных

***Запуск***

Собираем систему:
```
docker-compose build
```
Запускаем:
```
docker-compose up
```

Proxy сервер доступен по адресу *0.0.0.0:8080*. 

***Демо***

Можно запустить из папки `demo/` демонстрационный скрипт *demo.py* вручную, используя `python3 demo.py` или  докер:
```
docker build -t demo -f demo.dockerfile . && docker run --rm --network host demo
```

***Интерактивная версия***

Можно воспользоваться ncat для Linux (`sudo apt-get -y install ncat`):
```
ncat 0.0.0.0 8080 -u -v
```
Либо из папки `demo/` запустить скрипт *interactive.py*, используя `python3 interactive.py` или докер:
```
docker build -t interactive -f interactive.dockerfile . && docker run -i --rm --network host interactive
```

Далее пользователь может вводить запросы следующего формата:
```
get_result <формат сериализации>
форматы сериализации: native/xml/json/protobuf/avro/yaml/msgpack
(пример: get_result json)
для получения информации по конкретному формату
 
get_result all 
для получения информации по всем поддерживаемым форматам
```

***Результаты***

У меня локально получились такие результаты:
```
NATIVE   - 344  - 0.00677ms - 0.00752ms
XML      - 1216 - 0.51332ms - 0.65203ms
JSON     - 440  - 0.15009ms - 0.16258ms
PROTOBUF - 184  - 0.00094ms - 0.00154ms
AVRO     - 176  - 0.60557ms - 0.39879ms
YAML     - 448  - 2.32872ms - 5.71028ms
MSGPACK  - 216  - 0.00390ms - 0.00447ms
```
