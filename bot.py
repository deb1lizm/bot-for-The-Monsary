import discord
from discord import app_commands
from discord.ext import commands
import os
import json
import random

# --- Настройки ---
TOKEN = os.environ.get('BOT_TOKEN')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Файл для сохранения настроек приветствия
CONFIG_FILE = 'config.json'

# Хранилище активных игр "Угадай число" (user_id: загаданное_число)
active_guesses = {}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"hello_enabled": True}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# --- События ---

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Бот {bot.user} успешно запущен и готов к работе!')

@bot.event
async def on_member_join(member):
    config = load_config()
    if config.get("hello_enabled", True):
        channel = member.guild.system_channel
        if channel is not None:
            await channel.send(f"Привет, {member.mention}! Добро пожаловать на сервер! 🎉")
        else:
            try:
                await member.send(f"Привет! Добро пожаловать на сервер {member.guild.name}! 🎉")
            except discord.Forbidden:
                pass

# --- ИГРА: КРЕСТИКИ-НОЛИКИ ---

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        # Ставим крестик игрока
        self.label = '❌'
        self.style = discord.ButtonStyle.danger
        self.disabled = True
        self.view.board[self.x][self.y] = 'X'
        
        # Проверяем, не выиграл ли игрок
        winner = self.view.check_winner()
        if winner:
            await self.view.end_game(interaction, winner)
            return

        # Ход бота
        bot_move = self.view.get_bot_move()
        if bot_move:
            bx, by = bot_move
            self.view.children[bx * 3 + by].label = '⭕'
            self.view.children[bx * 3 + by].style = discord.ButtonStyle.primary
            self.view.children[bx * 3 + by].disabled = True
            self.view.board[bx][by] = 'O'

            # Проверяем, не выиграл ли бот
            winner = self.view.check_winner()
            if winner:
                await self.view.end_game(interaction, winner)
                return

        await interaction.response.edit_message(view=self.view)

class TicTacToeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        # Проверка строк, столбцов и диагоналей
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != ' ': return self.board[i][0]
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != ' ': return self.board[0][i]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != ' ': return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != ' ': return self.board[0][2]
        # Проверка на ничью
        if all(self.board[i][j] != ' ' for i in range(3) for j in range(3)):
            return 'Ничья'
        return None

    def get_bot_move(self):
        # 1. Попытка выиграть
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == ' ':
                    self.board[i][j] = 'O'
                    if self.check_winner() == 'O':
                        self.board[i][j] = ' '
                        return (i, j)
                    self.board[i][j] = ' '
        
        # 2. Попытка заблокировать игрока
        for i in range(3):
            for j in range(3):
                if self.board[i][j] == ' ':
                    self.board[i][j] = 'X'
                    if self.check_winner() == 'X':
                        self.board[i][j] = ' '
                        return (i, j)
                    self.board[i][j] = ' '

        # 3. Случайный ход (или центр)
        empty_cells = [(i, j) for i in range(3) for j in range(3) if self.board[i][j] == ' ']
        if empty_cells:
            return random.choice(empty_cells)
        return None

    async def end_game(self, interaction: discord.Interaction, winner: str):
        for child in self.children:
            child.disabled = True
        
        if winner == 'Ничья':
            await interaction.response.edit_message(content="🤝 Ничья! Хорошая игра.", view=self)
        elif winner == 'X':
            await interaction.response.edit_message(content="🎉 Ты победил! Поздравляю.", view=self)
        else:
            await interaction.response.edit_message(content="🤖 Бот победил! В следующий раз повезет больше.", view=self)

@bot.tree.command(name="tictactoe", description="Сыграть в крестики-нолики против бота")
async def tictactoe(interaction: discord.Interaction):
    await interaction.response.send_message("Игра началась! Твой ход (❌):", view=TicTacToeView())

# --- ИГРА: УГАДАЙ ЧИСЛО ---

@bot.tree.command(name="guessstart", description="Начать игру 'Угадай число'")
@app_commands.describe(max_number="Максимальное число для угадывания (например, 100)")
async def guessstart(interaction: discord.Interaction, max_number: int):
    if max_number < 2:
        await interaction.response.send_message("Максимальное число должно быть больше 1!", ephemeral=True)
        return
    
    secret_number = random.randint(1, max_number)
    active_guesses[interaction.user.id] = secret_number
    
    await interaction.response.send_message(
        f"Я загадал число от **1** до **{max_number}**. Попробуй угадать его с помощью команды `/guess`!", 
        ephemeral=True
    )

@bot.tree.command(name="guess", description="Твой вариант числа в игре 'Угадай число'")
@app_commands.describe(number="Число, которое ты предполагаешь")
async def guess(interaction: discord.Interaction, number: int):
    if interaction.user.id not in active_guesses:
        await interaction.response.send_message("Ты еще не начал игру! Используй `/guessstart`.", ephemeral=True)
        return
    
    secret = active_guesses[interaction.user.id]
    
    if number < secret:
        await interaction.response.send_message(f"📉 Мое число **больше** чем {number}.", ephemeral=True)
    elif number > secret:
        await interaction.response.send_message(f"📈 Мое число **меньше** чем {number}.", ephemeral=True)
    else:
        del active_guesses[interaction.user.id] # Удаляем игру после победы
        await interaction.response.send_message(f"🎉 Бинго! Ты угадал число **{secret}**!", ephemeral=True)

# --- АДМИН КОМАНДЫ ---

@bot.tree.command(name="hello", description="Включить или выключить приветствие новых участников")
@app_commands.describe(state="Включить (on) или выключить (off)")
@app_commands.choices(state=[
    app_commands.Choice(name="on", value="on"),
    app_commands.Choice(name="off", value="off")
])
@app_commands.default_permissions(administrator=True)
async def hello(interaction: discord.Interaction, state: app_commands.Choice[str]):
    config = load_config()
    if state.value == "on":
        config["hello_enabled"] = True
        await interaction.response.send_message("✅ Приветствие новых участников **включено**.", ephemeral=True)
    else:
        config["hello_enabled"] = False
        await interaction.response.send_message("❌ Приветствие новых участников **выключено**.", ephemeral=True)
    save_config(config)

# --- Запуск ---
if TOKEN:
    bot.run(TOKEN)
else:
    print("ОШИБКА: Переменная BOT_TOKEN не найдена!")