# Практика 2. Разработка приложения на основе gRPC

***Запуск***

Собираем систему:
```
docker-compose build
```
Запускаем:
```
docker-compose up
```

Mafia сервер доступен по адресу *server:50051* внутри сети докера prac3_mafia_network и по адресу *0.0.0.0:50051* в случае запуска вручную.

В docker-compose по умолчанию запускается сервер и 4 игрока-бота. Посмотреть журнал этих игроков можно используя *docker logs* и имя контейнера, например:
```
docker logs prac3_client1 | less
```

***Интерактивная версия***

Запуск интерактивного клиента *interactive/interactive.py* используя докер:

Собираем:
```
docker build -t prac3_interactive -f interactive/interactive.dockerfile .
```
Запускаем:
```
xhost local:root && docker run --rm -it -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix --network prac3_mafia_network prac3_interactive
```

Пользователю предлагается ввести адрес сервера в формате *host:port* и его имя. Имя должно быть уникальным и не содержать пробелов.

При наличии минимального необходимого числа игроков сервер начнет игру. Игрок получает случайно роль Мафия, Детектив или Мирный. В зависимости от роли, каждую ночь ему будет предложено либо проверить другого игрока, либо устранить, в случае роли Мафия.

Ночью игроки с ролью Мафия могут общаться друг с другом, при этом остальным игрокам их сообщения не видны. После каждой ночи начинается обсуждение в котором участвуют все живые игроки. Если Детектив ранее определил игрока Мафию, то он может сказать об этом, используя команду */publish* в чате.

После завершения обсуждения игрок может либо голосовать за продолжение

```
continue
```

либо против другого игрока

```
vote "username"
```

Игрок с наибольшим количеством голосов выбывает.

Игра заканчивается когда Мирным и Детективу удается определить и выгнать игрока с ролью Мафия, либо когда Мафия остается один на один с игроком Мирный или Детектив.

***Чат***

Чат основан на *RabbitMQ*, для обработки ввода пользователя используется библиотека *tkinter*. Пользователь может отправить сообщения в чат, введя текст в диалоговом окне, или выйти из него, закрыв диалоговое окно (или отправив команду */continue*).