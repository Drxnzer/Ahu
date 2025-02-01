import discord, tls_client, threading, os, requests, json, aiohttp, yaml, asyncio, platform, shutil, secrets
from base64 import b64encode
from discord import app_commands, File
from discord.ext import commands, tasks
from datetime import datetime
from discord.ui import Button, View, Modal, TextInput
import random
import string
intents = discord.Intents.all()

bot = commands.Bot(command_prefix='/', intents=intents)
if not hasattr(bot, 'tree'):
     bot.tree = app_commands.CommandTree(bot)

def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    elif platform.system() in ["Linux", "Darwin"]:
        os.system("clear")

@bot.event
async def on_ready():
    clear_screen()
    await bot.tree.sync()
    print(f'We have logged in as {bot.user}')
if not hasattr(bot, 'tree'):
    bot.tree = app_commands.CommandTree(bot)

with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

WEBHOOK_URL = config['webhook_url']
client_id = config['client_id']
secret = config['client_secret']
tkn = config['bot_token']
redirect = config['redirect_url']
OWNERS = config['owners']

def is_owner(user_id):
    return str(user_id) in OWNERS

@bot.tree.command(name='help', description="Get a list of all available bot commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Boost Bot | Help Command", description="", color=discord.Color.blue())
    embed.add_field(name="/redeem", value="Redeem tokens using a key.\nUsage: `/redeem [key] [server_id] [nickname: optional] [bio: optional]`", inline=False)
    embed.add_field(name="/stock", value="Show the current number of tokens in stock.\nUsage: `/stock [type: 1m|3m]`", inline=False)
    embed.add_field(name="Invite Bot", value=f"[Click here to invite Boost Bot](https://discord.com/oauth2/authorize?client_id={client_id}&permissions=2049&integration_type=0&scope=bot)", inline=False)
    embed.add_field(name="For Owner", value="Only For Owner")
    embed.add_field(name="/redeem-panel", value="Setup the redeem panel for users to claim boosts using a key.\nUsage: `/redeem-panel [channel]`", inline=False)
    embed.add_field(name="/create-keys", value="Generate keys and send them in a text file to your DM.\nUsage: `/create-keys [type: 1m|3m] [key_amount] [token_amount]`", inline=False)
    embed.add_field(name="/check-key", value="Check if the key is valid and get its information.\nUsage: `/check-key [key]`", inline=False)
    embed.add_field(name="/send-tokens", value="Send a specified amount of tokens to a user from a text file.\nUsage: `/send-tokens [type: 1m|3m] [user] [token_amount]`", inline=False)
    embed.add_field(name="/live-stock", value="View the current live stock of tokens\nUsage: `/live-stock [channel: optional]`", inline=False)
    embed.add_field(name="/restock", value="Restock tokens from using a uploaded file or a paste.ee raw link.\nUsage: `/restock [file/link] [type: 1m|3m]`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='create-keys', description="Generate keys and send them in a text file to your DM")
@app_commands.describe(
    key_amount="The number of keys to generate", 
    token_amount="The number of tokens per key"
)
@app_commands.choices(type=[
    app_commands.Choice(name="1 Month", value="1m"),
    app_commands.Choice(name="3 Month", value="3m")
])
async def create_keys(interaction: discord.Interaction, type: app_commands.Choice[str], key_amount: int, token_amount: int):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.")
        return

    filename = '1m.txt' if type.value == '1m' else '3m.txt'
    generated_keys = []
    genned_stocks_dir = "stock"

    if not os.path.exists(genned_stocks_dir):
        os.makedirs(genned_stocks_dir)

    with open(filename, 'r') as f:
        lines = f.readlines()

    total_tokens_needed = key_amount * token_amount
    if len(lines) < total_tokens_needed:
        await interaction.response.send_message(f"Not enough tokens in {type.name} stock to generate {key_amount} keys with {token_amount} tokens each.")
        return

    for _ in range(key_amount):
        key = (
    ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    + "-"
    + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    + "-"
    + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    + "-"
    + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4)))
        generated_keys.append(key)
        token_slice = lines[:token_amount]
        lines = lines[token_amount:]

        key_folder = os.path.join(genned_stocks_dir, key)
        os.makedirs(key_folder, exist_ok=True)

        token_file_path = os.path.join(key_folder, f"{type.value}.txt")
        with open(token_file_path, 'w') as f:
            f.writelines(token_slice)

    with open(filename, 'w') as f:
        f.writelines(lines)

    keys_file_path = os.path.join(genned_stocks_dir, f"{interaction.user.id}_keys.txt")
    with open(keys_file_path, 'w') as keys_file:
        for key in generated_keys:
            keys_file.write(f"{key}\n")

    user = await bot.fetch_user(interaction.user.id)
    try:
        await user.send(file=discord.File(keys_file_path))
        await interaction.response.send_message(f"Generated {key_amount} keys and sent them in a text file to your DM.")
    except discord.Forbidden:
        await interaction.response.send_message("I couldn't DM you. Please make sure your DMs are open.")

    os.remove(keys_file_path)

@bot.tree.command(name='restock', description="Restock tokens using a file or a Paste.ee link.")
@app_commands.describe(
    file="The file containing tokens to restock.",
    link="Paste.ee link or code.",
    type="The type of tokens: '1 Month' or '3 Month'."
)
@app_commands.choices(type=[
    app_commands.Choice(name="1 Month", value="1m"),
    app_commands.Choice(name="3 Month", value="3m")
])
async def restock(interaction: discord.Interaction, type: app_commands.Choice[str], file: discord.Attachment = None, link: str = None):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.")
        return

    if not file and not link:
        await interaction.response.send_message("You need to provide either a file or a Paste.ee link/code!")
        return

    stock_tokens = []

    if file:
        file_content = await file.read()
        stock_tokens = file_content.decode('utf-8').splitlines()

    elif link:
        if "paste.ee" in link:
            raw_paste_link = link.replace("https://paste.ee/p/", "https://paste.ee/r/")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(raw_paste_link) as response:
                        if response.status == 200:
                            paste_content = await response.text()
                            stock_tokens = paste_content.splitlines()
                        else:
                            await interaction.response.send_message("Failed to retrieve tokens from the provided Paste.ee link.")
                            return
            except Exception as e:
                await interaction.response.send_message(f"Error fetching Paste.ee content: {e}")
                return
        else:
            stock_tokens = link.splitlines()

    filename = '1m.txt' if type.value == '1m' else '3m.txt'

    with open(filename, 'a') as f:
        for token in stock_tokens:
            f.write(f"{token}\n")

    await interaction.response.send_message(f"Successfully added {len(stock_tokens)} tokens to the {type.name} stock.")

@bot.tree.command(name='stock', description="View the current stock of tokens")
@app_commands.describe(
    type="Select the type of tokens to view the stock count"
)
@app_commands.choices(type=[
    app_commands.Choice(name="1 Month", value="1m"),
    app_commands.Choice(name="3 Month", value="3m")
])
async def stock(interaction: discord.Interaction, type: app_commands.Choice[str]):
    filename = '1m.txt' if type.value == '1m' else '3m.txt'

    if os.path.exists(filename):
        with open(filename, 'r') as f:
            main_file_lines = f.readlines()
        total_stocks = len(main_file_lines)
    else:
        total_stocks = 0

    if type.value == '1m':
        additional_tokens = 0
        stock_dir = 'stock'

        for folder_name in os.listdir(stock_dir):
            folder_path = os.path.join(stock_dir, folder_name)
            if os.path.isdir(folder_path):
                file_path = os.path.join(folder_path, '1m.txt')
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        additional_lines = f.readlines()
                    additional_tokens += len(additional_lines)

        total_stocks += additional_tokens

    embed = discord.Embed(title="Stock", color=discord.Color.purple())
    embed.add_field(name=f"{type.name} Tokens", value=f"{total_stocks} tokens", inline=False)
    await interaction.response.send_message(embed=embed)
class InviteButton(discord.ui.View):
    def __init__(self, invite_link):
        super().__init__()
        self.invite_link = invite_link
        self.add_item(discord.ui.Button(
            label="Invite Application",
            style=discord.ButtonStyle.link,
            url=self.invite_link
        ))

@bot.tree.command(name='invite', description="Get an invite link of the bot")
async def invite_command(interaction: discord.Interaction):
    client_id = bot.user.id
    invite_link = f"https://discord.com/oauth2/authorize?client_id={client_id}&permissions=2049&integration_type=0&scope=bot"
    
    embed = discord.Embed(
        title="Invite Boost Bot",
        description=f"Invite our application to boost your server",
        color=discord.Color.blue()
    )
    
    view = InviteButton(invite_link)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name='send-tokens', description="Send nitro token(s) to a user from stock")
@app_commands.describe(
    type="Select the type of tokens (1 Month or 3 Month)",
    user="The user to whom the tokens will be sent",
    token_amount="The number of tokens to send"
)
@app_commands.choices(type=[
    app_commands.Choice(name="1 Month", value="1m"),
    app_commands.Choice(name="3 Month", value="3m")
])
async def send_tokens(interaction: discord.Interaction, type: app_commands.Choice[str], user: discord.User, token_amount: int):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.")
        return

    filename = '1m.txt' if type.value == '1m' else '3m.txt'

    if not os.path.exists(filename):
        await interaction.response.send_message(f"The stock file {filename} does not exist.", ephemeral=True)
        return

    with open(filename, 'r') as f:
        lines = f.readlines()

    if token_amount > len(lines):
        await interaction.response.send_message("Not enough tokens in stock.", ephemeral=True)
        return

    tokens_to_send = lines[:token_amount]
    remaining_tokens = lines[token_amount:]

    with open(filename, 'w') as f:
        f.writelines(remaining_tokens)

    sent_tokens_dir = './sent-tokens/'
    os.makedirs(sent_tokens_dir, exist_ok=True)

    sent_tokens_filename = os.path.join(sent_tokens_dir, f"{user.name}_tokens.txt")
    
    with open(sent_tokens_filename, 'w') as f:
        f.writelines(tokens_to_send)

    try:
        await user.send(f"You have received {token_amount} , {type.name} nitro token(s), you may find the tokens in the file attached below.", file=discord.File(sent_tokens_filename))
    except discord.Forbidden:
        await interaction.response.send_message(f"Could not send tokens to {user.mention}. They have DM's disabled.", ephemeral=True)
        return

    await interaction.response.send_message(f"{token_amount} , {type.name} token(s) have been sent to {user.mention}.", ephemeral=True)

class RedeemModal(Modal):
    def __init__(self):
        super().__init__(title="Redeem Tokens")

        self.key = TextInput(label="Key", placeholder="Enter your redeem key", required=True)
        self.server_id = TextInput(label="Server ID", placeholder="Enter the server ID", required=True)
        self.nickname = TextInput(label="Nickname (Optional)", placeholder="Enter a nickname", required=False)
        self.bio = TextInput(label="Bio (Optional)", placeholder="Enter a bio", required=False)

        self.add_item(self.key)
        self.add_item(self.server_id)
        self.add_item(self.nickname)
        self.add_item(self.bio)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value
        server_id = self.server_id.value
        nickname = self.nickname.value if self.nickname.value else None
        bio = self.bio.value if self.bio.value else None

        await interaction.response.defer()
        await process_redeem(interaction, key, server_id, nickname, bio)

async def process_redeem(interaction: discord.Interaction, key: str, server_id: str, nickname: str = None, bio: str = None):
    key_folder = os.path.join("stock", key)
    if not os.path.exists(key_folder):
        await interaction.followup.send("Invalid key! Please check and try again.", ephemeral=True)
        return

    token_files = [f for f in os.listdir(key_folder) if f.endswith('.txt')]
    if not token_files:
        await interaction.followup.send("No tokens available found for the provided key.", ephemeral=True)
        return

    tokens_used = 0
    successful_boosts = 0
    failed_tokens = 0
    joined_guilds = 0
    successful_tokens = []
    failed_token_list = []
    success_boost_list = []

    def redeem_token(token, server_id, nickname=None, bio=None):
        tk = token.split(":")[2]
        try:
            authorizer(tk, server_id, nickname, bio)
            headers = get_headers(tk, __properties__, __useragent__)
            client = tls_client.Session(client_identifier="firefox_102")
            client.headers.update(headers)

            r = client.get(f"{API_ENDPOINT}/users/@me/guilds/premium/subscription-slots")
            idk = r.json()

            boost_count = 0
            for x in idk:
                if boost_count >= 2:
                    break
                id_ = x['id']
                payload = {"user_premium_guild_subscription_slot_ids": [id_]}
                r = client.put(f"{API_ENDPOINT}/guilds/{server_id}/premium/subscriptions", json=payload)

                if r.status_code in (200, 201, 204):
                    boost_count += 1
                elif r.status_code == 429:
                    return "Cooldown", tk
                else:
                    return f"Boost failed: {r.status_code} - {r.text}", tk

            if boost_count == 2:
                return "boosted twice", tk
            else:
                return "joined", tk
        except Exception as e:
            return f"Failed: {str(e)}", token

    for token_file in token_files:
        with open(os.path.join(key_folder, token_file), 'r') as f:
            tokens = f.readlines()

        for token in tokens:
            token = token.strip()
            result, tk = redeem_token(token, server_id, nickname, bio)
            if result == "joined":
                joined_guilds += 1
                successful_tokens.append(tk)
            elif result == "boosted twice":
                successful_boosts += 2
                success_boost_list.append(tk)
                tokens_used += 1
            elif result == "Cooldown":
                failed_tokens += 1
                failed_token_list.append(f"{tk} - Cooldown active")
            else:
                failed_tokens += 1
                failed_token_list.append(f"{tk} - {result if result else 'Unknown Error'}")

    guild_info = await bot.fetch_guild(server_id)
    server_name = guild_info.name
    user_name = interaction.user.name
    user_id = interaction.user.id
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    webhook_payload = {
        "embeds": [
            {
                "title": "Boosts Redeemed",
                "color": 0x800080,
                "fields": [
                    {"name": "Key", "value": key, "inline": False},
                    {"name": "Server", "value": f"{server_name} ({server_id})", "inline": False},
                    {"name": "Redeemed by", "value": f"{user_name} ({user_id})", "inline": False},
                    {"name": "Tokens Used", "value": f"{tokens_used} tokens", "inline": False},
                    {"name": "Successful Boosts", "value": f"{successful_boosts} boosts", "inline": False},
                    {"name": "Failed Tokens", "value": f"{failed_tokens} tokens", "inline": False},
                    {"name": "Timestamp", "value": timestamp, "inline": False},
                ]
            }
        ]
    }

    requests.post(WEBHOOK_URL, json=webhook_payload)

    shutil.rmtree(key_folder)
    await interaction.followup.send(f"Tokens have been redeemed and added to server ID: {server_id}", ephemeral=True)

class RedeemView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="Redeem", style=discord.ButtonStyle.green, custom_id="redeem_button"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        modal = RedeemModal()
        await interaction.response.send_modal(modal)
        return True

@bot.tree.command(name='redeem-panel', description="Set up the redeem panel")
@app_commands.describe(channel="The channel where to send the redeem panel")
async def redeem_panel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.")
        return

    embed = discord.Embed(
        title="Redeem Panel",
        description="Click the button below to redeem your tokens. \n\n**Note:** Ensure you have added our bot to the server before using the key.\nAdd your Server ID and optional Nickname/Bio.",
        color=0x00FF00
    )
    embed.set_footer(text="Boost Bot")
    embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1286293921328136204/ff173ae8024d201b9cf2bfa1f24c107b.png?size=1024")

    view = RedeemView()
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"Redeem panel sent to {channel.mention}", ephemeral=True)

@bot.tree.command(name='redeem', description="Redeem tokens using a key")
@app_commands.describe(key="The key for redeeming tokens", server_id="The server ID where tokens will join", nickname="Optional nickname for the tokens", bio="Optional bio for the tokens")
async def redeem_tokens(interaction: discord.Interaction, key: str, server_id: str, nickname: str = None, bio: str = None):
    await interaction.response.defer()

    key_folder = os.path.join("stock", key)
    if not os.path.exists(key_folder):
        await interaction.followup.send("Invalid key! Please check and try again.")
        return

    token_files = [f for f in os.listdir(key_folder) if f.endswith('.txt')]
    if not token_files:
        await interaction.followup.send("No tokens available found for the provided key.")
        return

    tokens_used = 0
    successful_boosts = 0
    failed_tokens = 0
    joined_guilds = 0
    failed_token_list = []
    successful_tokens = []
    success_boost_list = []

    def redeem_token(token, server_id, nickname=None, bio=None):
        tk = token.split(":")[2]
        try:
            authorizer(tk, server_id, nickname, bio) 
            headers = get_headers(tk, __properties__, __useragent__)
            client = tls_client.Session(client_identifier="firefox_102")
            client.headers.update(headers)

            r = client.get(f"{API_ENDPOINT}/users/@me/guilds/premium/subscription-slots")
            slots = r.json()

            boost_count = 0
            for slot in slots:
                id_ = slot['id']
                payload = {"user_premium_guild_subscription_slot_ids": [id_]}
                r = client.put(f"{API_ENDPOINT}/guilds/{server_id}/premium/subscriptions", json=payload)

                if r.status_code in (200, 201, 204):
                    boost_count += 1
                    if boost_count == 2:
                        return "boosted", tk
                elif r.status_code == 429:
                    return "Cooldown", tk
                else:
                    return f"Boost failed: {r.status_code} - {r.text}", tk

            if boost_count == 1:
                return "only 1 boost", tk
            return "joined", tk
        except Exception as e:
            return f"Failed: {str(e)}", token

    for token_file in token_files:
        with open(os.path.join(key_folder, token_file), 'r') as f:
            tokens = f.readlines()

        for token in tokens:
            token = token.strip()
            result, tk = redeem_token(token, server_id, nickname, bio)
            if result == "joined":
                joined_guilds += 1
                successful_tokens.append(tk)
            elif result == "boosted":
                successful_boosts += 2
                success_boost_list.append(tk)
                tokens_used += 1
            elif result == "only 1 boost":
                successful_boosts += 1
                success_boost_list.append(f"{tk} - Only 1 boost applied")
                tokens_used += 1
            elif result == "Cooldown":
                failed_tokens += 1
                failed_token_list.append(f"{tk} - Cooldown active")
            else:
                failed_tokens += 1
                failed_token_list.append(f"{tk} - {result if result else 'Unknown Error'}")

    guild_info = await bot.fetch_guild(server_id)
    server_name = guild_info.name
    user_name = interaction.user.name
    user_id = interaction.user.id

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    webhook_payload = {
        "content": ".",
        "embeds": [
            {
                "title": "Boosts Redeemed",
                "color": 0x800080,
                "fields": [
                    {"name": "Key", "value": key, "inline": False},
                    {"name": "Server", "value": f"{server_name} ({server_id})", "inline": False},
                    {"name": "Redeemed by", "value": f"{user_name} ({user_id})", "inline": False},
                    {"name": "Tokens Used", "value": f"{tokens_used} tokens", "inline": False},
                    {"name": "Successful Boosts", "value": f"{successful_boosts} boosts", "inline": False},
                    {"name": "Failed Tokens", "value": f"{failed_tokens} tokens", "inline": False},
                    {"name": "Timestamp", "value": timestamp, "inline": False},
                ]
            }
        ]
    }
    requests.post(WEBHOOK_URL, json=webhook_payload)

    shutil.rmtree(key_folder)
    await interaction.followup.send(f"Tokens have been redeemed and added to server ID: {server_id}")

__useragent__ = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
build_number = 165486
cv = "108.0.0.0"
API_ENDPOINT = 'https://canary.discord.com/api/v9'
auth = f"https://canary.discord.com/api/oauth2/authorize?client_id={client_id}&redirect_uri={redirect}&response_type=code&scope=identify%20guilds.join"

__properties__ = b64encode(
    json.dumps({
        "os": "Windows",
        "browser": "Chrome",
        "device": "PC",
        "system_locale": "en-GB",
        "browser_user_agent": __useragent__,
        "browser_version": cv,
        "os_version": "10",
        "referrer": "https://discord.com/channels/@me",
        "referring_domain": "discord.com",
        "referrer_current": "",
        "referring_domain_current": "",
        "release_channel": "stable",
        "client_build_number": build_number,
        "client_event_source": None
    }, separators=(',', ':')).encode()).decode()

def get_headers(token, super_properties, user_agent):
    headers = {
        "Authorization": token,
        "Origin": "https://canary.discord.com",
        "Accept": "*/*",
        "X-Discord-Locale": "en-GB",
        "X-Super-Properties": super_properties,
        "User-Agent": user_agent,
        "Referer": "https://canary.discord.com/channels/@me",
        "X-Debug-Options": "bugReporterEnabled",
        "Content-Type": "application/json"
    }
    return headers

def exchange_code(code):
    data = {
        'client_id': client_id,
        'client_secret': secret,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(f"{API_ENDPOINT}/oauth2/token", data=data, headers=headers)
    
    if r.status_code in (200, 201, 204):
        return r.json()
    else:
        print(f"[ERROR] Failed to exchange code: {r.status_code} - {r.text}")
        return False

def add_to_guild(access_token, userID, guild):
    url = f"{API_ENDPOINT}/guilds/{guild}/members/{userID}"
    botToken = tkn
    data = {"access_token": access_token}
    headers = {"Authorization": f"Bot {botToken}", 'Content-Type': 'application/json'}
    
    r = requests.put(url=url, headers=headers, json=data)
    
    if r.status_code in (200, 201, 204):
        print(f"[+] User {userID} added to guild {guild}")
    else:
        print(f"[ERROR] Failed to add user to guild: {r.status_code} - {r.text}")
    
    return r.status_code

def rename(tk, guild, nickname):
    headers = get_headers(tk, __properties__, __useragent__)
    client = tls_client.Session(client_identifier="firefox_102")
    client.headers.update(headers)
    
    r = client.patch(f"{API_ENDPOINT}/guilds/{guild}/members/@me", json={"nick": nickname})
    
    if r.status_code in (200, 201, 204):
        print("[+] Nickname updated successfully")
        return "ok"
    else:
        print(f"[ERROR] Failed to update nickname: {r.status_code} - {r.text}")
        return "error"

def update_bio(tk, bio):
    headers = get_headers(tk, __properties__, __useragent__)
    client = tls_client.Session(client_identifier="firefox_102")
    client.headers.update(headers)
    
    r = client.patch(f"{API_ENDPOINT}/users/@me/profile", json={"bio": bio})
    
    if r.status_code in (200, 201, 204):
        print("[+] Bio updated successfully")
        return "ok"
    else:
        print(f"[ERROR] Failed to update bio: {r.status_code} - {r.text}")
        return "error"

def authorizer(tk, guild, nickname, bio):
    headers = get_headers(tk, __properties__, __useragent__)
    r = requests.post(auth, headers=headers, json={"authorize": "true"})
    
    if r.status_code in (200, 201, 204):
        location = r.json().get('location', "")
        code = location.replace("http://localhost:8080?code=", "")
        exchange = exchange_code(code)
        
        if exchange:
            access_token = exchange.get('access_token', "")
            user_id = get_user(access_token)
            add_to_guild(access_token, user_id, guild)
            
            if nickname:
                threading.Thread(target=rename, args=(tk, guild, nickname)).start()
            
            if bio:
                threading.Thread(target=update_bio, args=(tk, bio)).start()
            return "ok"
    else:
        print(f"[ERROR] Authorization failed: {r.status_code} - {r.text}")
        return "error"

def get_user(access: str):
    r = requests.get(f"{API_ENDPOINT}/users/@me", headers={"Authorization": f"Bearer {access}"})
    rjson = r.json()
    
    if 'id' in rjson:
        return rjson['id']
    else:
        print(f"[ERROR] Failed to fetch user: {r.status_code} - {r.text}")
        return None

def main(tk, guild, nickname=None, bio=None):
    authorizer(tk, guild, nickname, bio)
    headers = get_headers(tk, __properties__, __useragent__)
    client = tls_client.Session(client_identifier="firefox_102")
    client.headers.update(headers)
    
    r = client.get(f"{API_ENDPOINT}/users/@me/guilds/premium/subscription-slots")
    idk = r.json()
    
    for x in idk:
        id_ = x['id']
        payload = {"user_premium_guild_subscription_slot_ids": [id_]}
        
        r = client.put(f"{API_ENDPOINT}/guilds/{guild}/premium/subscriptions", json=payload)
        
        if r.status_code in (200, 201, 204):
            print(f"[+] Boosted guild {guild} successfully")
        else:
            print(f"[ERROR] Failed to boost guild: {r.status_code} - {r.text}")

@bot.event
async def on_guild_join(guild):
    guild_name = guild.name
    guild_id = guild.id
    owner = guild.owner
    owner_name = owner.name
    owner_id = owner.id
    created_at = guild.created_at.strftime("%Y-%m-%d %H:%M:%S")

    invite = await guild.text_channels[0].create_invite(max_age=0, max_uses=0, unique=True)
    invite_link = invite.url

    embed = {
        "title": "New Guild Joined",
        "color": discord.Color.blue().value,
        "fields": [
            {"name": "Guild Name", "value": guild_name, "inline": True},
            {"name": "Guild ID", "value": guild_id, "inline": True},
            {"name": "Owner Name", "value": owner_name, "inline": True},
            {"name": "Owner ID", "value": owner_id, "inline": True},
            {"name": "Created At", "value": created_at, "inline": False},
            {"name": "Invite Link", "value": invite_link, "inline": False},
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }

    data = {
        "username": "Guild Logger",
        "embeds": [embed],
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(WEBHOOK_URL, json=data, headers=headers)

    if response.status_code == 204:
        print(f"Successfully sent guild join log to webhook for guild {guild_name} with ID {guild_id}")
    else:
        print(f"Failed to send guild join log for guild {guild_name} with ID {guild_id}: {response.status_code} - {response.text}")

def is_key_valid(key):
    """Check if a key is valid based on the existence of the directory."""
    key_folder = os.path.join("stock", key)
    return os.path.exists(key_folder)

async def boost_server(key, server_id, nickname=None, bio=None):
    key_folder = os.path.join("stock", key)
    if not is_key_valid(key):
        return {'status': 'error', 'message': 'Invalid key'}

    token_files = [f for f in os.listdir(key_folder) if f.endswith('.txt')]
    if not token_files:
        return {'status': 'error', 'message': 'No tokens found for the provided key'}

    tokens_used, successful_boosts, failed_tokens, joined_guilds = 0, 0, 0, 0
    failed_token_list, successful_tokens, success_boost_list = [], [], []

    def redeem_token(token, server_id, nickname, bio):
        tk = token.split(":")[2]
        try:
            authorizer(tk, server_id, nickname, bio) 
            headers = get_headers(tk, __properties__, __useragent__)
            client = tls_client.Session(client_identifier="firefox_102")
            client.headers.update(headers)
            
            r = client.get(f"{API_ENDPOINT}/users/@me/guilds/premium/subscription-slots")
            idk = r.json()
            
            for x in idk:
                id_ = x['id']
                payload = {"user_premium_guild_subscription_slot_ids": [id_]}
                r = client.put(f"{API_ENDPOINT}/guilds/{server_id}/premium/subscriptions", json=payload)
                
                if r.status_code in (200, 201, 204):
                    return "boosted", tk
                elif r.status_code == 429:
                    return "Cooldown", tk
                else:
                    return f"Boost failed: {r.status_code} - {r.text}", tk
            return "joined", tk
        except Exception as e:
            return f"Failed: {str(e)}", token

    for token_file in token_files:
        with open(os.path.join(key_folder, token_file), 'r') as f:
            tokens = f.readlines()

        for token in tokens:
            token = token.strip()
            result, tk = redeem_token(token, server_id, nickname, bio)
            if result == "joined":
                joined_guilds += 1
                successful_tokens.append(tk)
            elif result == "boosted":
                successful_boosts += 2
                success_boost_list.append(tk)
                tokens_used += 1
            elif result == "Cooldown":
                failed_tokens += 1
                failed_token_list.append(f"{tk} - Cooldown active")
            else:
                failed_tokens += 1
                failed_token_list.append(f"{tk} - {result if result else 'Unknown Error'}")
    
    guild_info = await bot.fetch_guild(int(server_id))
    server_name = guild_info.name
    user_name = "Web User"
    user_id = config["client_id"]

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    webhook_payload = {
        "content": ".",
        "embeds": [
            {
                "title": "Boosts Redeemed",
                "color": 0x800080,
                "fields": [
                    {"name": "Key", "value": key, "inline": False},
                    {"name": "Server", "value": f"{server_name} ({server_id})", "inline": False},
                    {"name": "Redeemed by", "value": f"{user_name} ({user_id})", "inline": False},
                    {"name": "Tokens Used", "value": f"{tokens_used} tokens", "inline": False},
                    {"name": "Successful Boosts", "value": f"{successful_boosts} boosts", "inline": False},
                    {"name": "Failed Tokens", "value": f"{failed_tokens} tokens", "inline": False},
                    {"name": "Timestamp", "value": timestamp, "inline": False},
                ]
            }
        ]
    }
    requests.post(WEBHOOK_URL, json=webhook_payload)

    shutil.rmtree(key_folder)
    return {'status': 'success', 'boosts': successful_boosts}

def check_stock(stock_file):
    if os.path.exists(stock_file):
        with open(stock_file, 'r') as f:
            lines = f.readlines()
        return len(lines)
    return 0

def check_stock(file_path):
    try:
        with open(file_path, 'r') as file:
            return len(file.readlines())
    except FileNotFoundError:
        return 0

def get_stock_info():
    stock_1m = check_stock('1m.txt')
    stock_3m = check_stock('3m.txt')

    stock_1m_additional_tokens = 0
    
    stock_dir = 'stock'

    for folder_name in os.listdir(stock_dir):
        folder_path = os.path.join(stock_dir, folder_name)
        if os.path.isdir(folder_path):
            file_path = os.path.join(folder_path, '1m.txt')
            stock_1m_additional_tokens += check_stock(file_path)
    
    total_stock_1m_tokens = stock_1m + stock_1m_additional_tokens

    return {
        "1m": {
            "boosts": total_stock_1m_tokens * 2,
            "tokens": total_stock_1m_tokens
        },
        "3m": {
            "boosts": stock_3m * 2,
            "tokens": stock_3m
        }
    }

@tasks.loop(seconds=90)
async def update_stock_embed(message):
    stock_info = get_stock_info()

    embed = discord.Embed(title="Live Stock", color=discord.Color.purple())
    embed.add_field(name="**1 Month**", value=f"```Boosts: {stock_info['1m']['boosts']} / Tokens: {stock_info['1m']['tokens']}```", inline=False)
    embed.add_field(name="**3 Month**", value=f"```Boosts: {stock_info['3m']['boosts']} / Tokens: {stock_info['3m']['tokens']}```", inline=False)
    await message.edit(embed=embed)
    
    for remaining in range(89, 0, -1):
        await message.edit(embed=embed)
        await asyncio.sleep(1)

    stock_info = get_stock_info()
    embed = discord.Embed(title="Live Stock", color=discord.Color.purple())
    embed.add_field(name="**1 Month**", value=f"```Boosts: {stock_info['1m']['boosts']} / Tokens: {stock_info['1m']['tokens']}```", inline=False)
    embed.add_field(name="**3 Month**", value=f"```Boosts: {stock_info['3m']['boosts']} / Tokens: {stock_info['3m']['tokens']}```", inline=False)
    await message.edit(embed=embed)

def is_key_valid(key):
    """Check if a key is valid based on the existence of the directory."""
    key_folder = os.path.join("stock", key)
    return os.path.exists(key_folder)

@bot.tree.command(name='check-key', description="Check if the key is valid and get its information")
@app_commands.describe(key="The key to check")
async def check_key(interaction: discord.Interaction, key: str):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.")
        return
    
    if not is_key_valid(key):
        await interaction.response.send_message("Invalid key! Please check and try again.")
        return
    
    key_folder = os.path.join("stock", key)
    
    tokens_file = None
    key_type = None
    if os.path.exists(os.path.join(key_folder, '1m.txt')):
        tokens_file = os.path.join(key_folder, '1m.txt')
        key_type = "1 Month"
    elif os.path.exists(os.path.join(key_folder, '3m.txt')):
        tokens_file = os.path.join(key_folder, '3m.txt')
        key_type = "3 Month"
    
    if tokens_file:
        with open(tokens_file, 'r') as file:
            tokens = file.readlines()
        total_tokens = len(tokens)
    else:
        total_tokens = 0
        tokens = []
    
    embed = discord.Embed(title="Key Information", color=discord.Color.blue())
    embed.add_field(name="Key", value=key, inline=False)
    embed.add_field(name="Key Type", value=key_type, inline=False)
    embed.add_field(name="Total Tokens", value=total_tokens, inline=False)
    
    await interaction.response.send_message(embed=embed)
    await interaction.followup.send(file=File(tokens_file))

@bot.tree.command(name='live-stock', description="View the current live stock of tokens")
@app_commands.describe(channel="The channel where the live stock will be shown")
async def live_stock(interaction: discord.Interaction, channel: discord.TextChannel = None):
    if not is_owner(interaction.user.id):
        await interaction.response.send_message("You do not have permission to use this command.")
        return

    target_channel = channel or interaction.channel

    stock_info = get_stock_info()
    embed = discord.Embed(title="Live Stock", color=discord.Color.purple())
    embed.add_field(name="**1 Month**", value=f"```Boosts: {stock_info['1m']['boosts']} / Tokens: {stock_info['1m']['tokens']}```", inline=False)
    embed.add_field(name="**3 Month**", value=f"```Boosts: {stock_info['3m']['boosts']} / Tokens: {stock_info['3m']['tokens']}```", inline=False)

    msg = await target_channel.send(embed=embed)
    update_stock_embed.start(msg)
bot.run(tkn)
