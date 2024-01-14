import telebot
import requests
from bs4 import BeautifulSoup
import libtorrent as lt
import tempfile
import os
import time

# Установите свой токен бота
TOKEN = '6958777588:AAG6Ly6WbOzDpCxNhaMx_MtItAgHi0KF-Dc'
bot = telebot.TeleBot(TOKEN)

def download_torrent(url, chat_id):
    # Создаем временный файл для сохранения торрент-файла
    _, torrent_filename = tempfile.mkstemp(suffix=".torrent")
    
    # Скачиваем торрент-файл
    with open(torrent_filename, 'wb') as torrent_file:
        response = requests.get(url)
        torrent_file.write(response.content)

    # Инициализируем сессию libtorrent
    ses = lt.session()
    ses.listen_on(6881, 6889)  # Устанавливаем порты для прослушивания в диапазоне 6881-6889
    ses.add_extension(lt.create_ut_metadata_plugin)
    ses.add_extension(lt.create_ut_pex_plugin)

    # Загружаем торрент-файл из диска
    info = lt.torrent_info(torrent_filename)
    h = ses.add_torrent({"ti": info, "save_path": "."})

    message = bot.send_message(chat_id, f"Downloading {h.name()}")
    while not h.is_seed():
        s = h.status()
        status_message = f'%.2f%% complete (down: %.1f kB/s up: %.1f kB/s peers: %d) {s.state}' % (
            s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000, s.num_peers)
        print(status_message)
        
        # Ждем 10 секунд перед следующим выводом
        time.sleep(1)
        bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=status_message)

        alerts = ses.pop_alerts()
        for alert in alerts:
            if alert.category() & lt.alert.category_t.error_notification:
                print(alert)

    # Отправляем ссылку на скачанный файл в Telegram
    downloaded_file_path = os.path.join(".", h.name())  # Предполагаем, что файл сохраняется в текущей директории
    download_link = f"http://172.187.90.13/{downloaded_file_path}"  # Замените на фактический URL или путь к файлу

    bot.send_message(chat_id, f"Загрузка {h.name()} завершена. Ссылка на скачанный файл: {download_link}")

    # Удаляем временный торрент-файл после завершения загрузки
    os.remove(torrent_filename)


def search_rutor(query):
    base_url = "https://rutor.info/search/"
    search_url = f"{base_url}{query}"

    # Отправляем GET-запрос на страницу поиска
    response = requests.get(search_url)

    results = []

    if response.status_code == 200:
        # Используем BeautifulSoup для парсинга HTML-кода
        soup = BeautifulSoup(response.content, 'html.parser')

        # Ищем все теги <tr> с классом "gai"
        result_rows = soup.find_all('tr', class_='gai')

        # Выводим информацию и абсолютные ссылки для скачивания
        for row in result_rows:
            date = row.find('td').text.strip()
            title_link = row.find('a', class_='downgif')
            title = title_link.text.strip()
            relative_url = title_link.get('href')
            absolute_url = f"https:{relative_url}"
            
            try:
                size = row.find_all('td', align='right')[1].text.strip()
            except IndexError:
                size = "Нет информации о размере"
            
            seeders = int(row.find('span', class_='green').text.strip())
            leechers = int(row.find('span', class_='red').text.strip())

            # Проверяем, что есть хотя бы один сидер
            if seeders > 0:
                search_result = (
                    f"Дата: {date}\n"
                    f"Размер: {size}\n"
                    f"Seeders: {seeders}\n"
                    f"Leechers: {leechers}"
                )

                results.append({"result": search_result, "url": absolute_url})

    return results

# Обработчик команды /start
@bot.message_handler(func=lambda message: True)
def handle_messages(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите запрос для поиска:")
    bot.register_next_step_handler(message, process_search_query)

def process_search_query(message):
    chat_id = message.chat.id
    search_query = message.text
    results = search_rutor(search_query)

    for index, result in enumerate(results):
        bot.send_message(chat_id, f"Результат {index + 1}:\n{result['result']}")

    if results:
        bot.send_message(chat_id, "Введите номер результата, чтобы скачать торрент:")

        bot.register_next_step_handler(message, process_download_option, results)
    else:
        bot.send_message(chat_id, "По вашему запросу ничего не найдено.")

def process_download_option(message, results):
    chat_id = message.chat.id
    try:
        selected_index = int(message.text) - 1
        selected_result = results[selected_index]

        download_option = bot.send_message(chat_id, "Хотите скачать торрент-файл? (y/n)")
        bot.register_next_step_handler(download_option, process_download_confirmation, selected_result)

    except (ValueError, IndexError):
        bot.send_message(chat_id, "Введите корректный номер результата.")

def process_download_confirmation(message, selected_result):
    chat_id = message.chat.id
    download_option = message.text.lower()

    if download_option == 'y':
        # Здесь нужно вызвать функцию для скачивания торрент-файла
        download_torrent(selected_result['url'], chat_id)
    else:
        bot.send_message(chat_id, "Ок, просто дайте знать, если вам нужно что-то еще.")

# Запуск бота
if __name__ == "__main__":
    bot.polling(none_stop=True)