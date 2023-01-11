import asyncio
import discord
from discord.ext import tasks
import asyncpg
import datetime
import re
from util import parseDate, RoomStates


class ArcClient(discord.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        self.pool: asyncpg.Pool = None
        self.debug_guilds = [844842869285847060]
        self.logging_channel = 988516254983802890
        self.category = 844887572307640331


client = ArcClient()
group = client.create_group("oda", "GTFO oda komutları")

allowPermisson = discord.PermissionOverwrite()
allowPermisson.connect = True
allowPermisson.speak = True

denyPermission = discord.PermissionOverwrite()
denyPermission.connect = False
denyPermission.speak = False


@group.command(name="oluştur", description="Oda oluşturun")
async def oda_olustur(ctx: discord.ApplicationContext, tarih: discord.Option(str, required=True, description="Şuandan itibaren ne kadar sonra başlamasını istediğinizi yazın. (5gün 3dk 2sn 21saat)"), bölüm: discord.Option(str, default="Herhangi"), kilit: discord.Option(bool, description="Oda açıldığında kilitlensin mi?", default=False)):
    if re.match("[0-9]{1,2}:[0-9]{1,2}", tarih):

        hour = tarih.split(":")[0]
        minute = tarih.split(":")[1]
        date = datetime.datetime.now()
        date = date.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    else:
        total, err = parseDate(tarih)
        if err is not None:
            return await ctx.respond(embed=errorEmbed("Tarih düzeni yanlış", err), ephemeral=True)
        date = datetime.datetime.now() + datetime.timedelta(seconds=total)
    async with client.pool.acquire() as db:
        await db.execute("insert into rooms(state, host, participants, date, rundown, lock) values($1, $2, $3, $4, $5, $6)", RoomStates.ACTIVE.id, ctx.author.id, [ctx.author.id], date, bölüm, kilit)
        room = await db.fetchrow("select * from rooms where host=$1 order by id desc", ctx.author.id)
    await ctx.respond(embed=successEmbed("Oda oluşturuldu", f"**Oda Numarası**: `{room['id']}`\n**Başlama Tarihi**: <t:{int(date.timestamp())}:R>"), ephemeral=True)
    await client.get_channel(client.logging_channel).send(embed=newRoomEmbed(room))

@group.command(name="sil", description="Hostladığınız bir odayı silin")
async def oda_sil(ctx: discord.ApplicationContext, id: discord.Option(int, required=True, description="Odanın id'si")):
    room = await getroombyid(id)
    if room is None:
        return await ctx.respond(embed=errorEmbed("Oda yok.", "Bu ID'ye sahip bir oda bulunmamakta."), ephemeral=True)
    if ctx.author.id != room["host"]:
        return await ctx.respond(embed=errorEmbed("Odanın host'u değilsiniz.", "Odaları sadece oda host'ları silebilir"), ephemeral=True)
    async with client.pool.acquire() as db:
        await db.execute("delete from rooms where id=$1", room['id'])
    await ctx.respond(embed=successEmbed("Oda silindi", f"Hostladığınız {id} numaralı odayı başarıyla sildiniz!"), ephemeral=True)


class RoomJoin(discord.ui.Button):
    def __init__(self, roomID, userID, roomData, page):
        self.room_id = roomID
        self.user_id = userID
        self.page = page
        super().__init__(style=discord.ButtonStyle.green)
        self.action_type = 0 if userID not in roomData["participants"] else 1
        self.label = "Odaya katıl" if self.action_type == 0 else "Odadan ayrıl"
        self.disabled = True if (self.action_type == 0 and len(roomData["participants"]) == 4) or roomData["state"] != 0 else False

    async def callback(self, interaction: discord.Interaction):
        room = await getroombyid(self.room_id)
        if len(room["participants"]) == 4:
            self.disabled = True
            await interaction.response.send_message(embed=errorEmbed("Oda dolu!", "Bu oda çoktan dolmuş Bu odaya katılamazsın."), ephemeral=True)
            return await self.view.message.edit(view=self.view)

        if self.action_type == 0:
            room["participants"].append(interaction.user.id)
            async with client.pool.acquire() as db:
                if len(room["participants"]) == 4:
                    await db.execute("update rooms set participants=$1, state=1 where id=$2", room["participants"], self.room_id)
                else:
                    await db.execute("update rooms set participants=$1 where id=$2", room["participants"], self.room_id)
            await interaction.response.send_message(embed=successEmbed("Odaya katıldın!", "Bu odaya katıldın. Oyunun başlayacağı tarihte sana bir ping atılacak!"), ephemeral=True)
            try:
                await client.get_user(room["host"]).send(f"{client.get_user(self.user_id).mention} `{room['id']}` numaralı odanıza katıldı.")
            except:
                pass
        else:
            if self.user_id == room["host"]:
                await interaction.response.send_message(embed=errorEmbed("Hata", "Kendi hostladığın odadan çıkamazsın!"), ephemeral=True)
                self.disabled = True
                return await self.view.message.edit(view=self.view)

            room["participants"].remove(interaction.user.id)
            async with client.pool.acquire() as db:
                await db.execute("update rooms set participants=$1, state=0 where id=$2", room["participants"], self.room_id)

            await interaction.response.send_message(embed=successEmbed("Odadan ayrıldın!", "Bu odadan ayrıldın."), ephemeral=True)
            try:
                await client.get_user(room["host"]).send(f"{client.get_user(self.user_id).mention} `{room['id']}` numaralı odanızdan ayrıldı.")
            except:
                pass
        embed = discord.Embed(title=f"{room['id']} numaralı oda")
        embed.colour = discord.Color.blurple()
        embed.description = f"**Oda Numarası**: `{room['id']}`\n**Oda Sahibi**: {client.get_user(room['host']).name}\n**Bölüm**: {room['rundown']}\n**Katılımcılar**: {', '.join([user.mention for user in [client.get_user(user) for user in room['participants']]])}\n**Durum**: {RoomStates.fromId(room['state']).desc}\n**Başlama Tarihi**: <t:{int(room['date'].timestamp())}:R>"
        await self.view.message.edit(embed=embed, view=RoomView(room, self.user_id, self.page,self.view.message))


class RoomView(discord.ui.View):
    def __init__(self, roomdata, user_id, page, message = None):
        super().__init__()
        if message is not None:
            self.message = message
        self.page = page
        self.add_item(RoomJoin(roomdata["id"], user_id, roomdata, self.page))

    @discord.ui.button(label="Geri dön", style=discord.ButtonStyle.red)
    async def callback(self, button, interaction):
        embed = discord.Embed(title="Odalar", colour=discord.Colour.blurple(), description="")
        rooms = await getroomsbypage(self.page)
        for room in rooms:
            embed.description += getRoomText(room) + "\n\n"
        embed.description = embed.description[:-2]
        embed.set_footer(text=client.user.name + " | Oda Sistemi | Sayfa " + str(self.page+1),
                         icon_url=client.user.avatar.url)
        count = await getcount()
        await interaction.response.edit_message(embed=embed, view=RoomSearchView(rooms, self.page, count // 5 + (1 if count % 5 != 0 else 0)))


class RoomSelect(discord.ui.Select):
    def __init__(self, data):
        super().__init__(placeholder="Oda seç")
        for roomdata in data:
            host = client.get_user(roomdata["host"])
            self.add_option(label=f"Oda {roomdata['id']}", value=str(roomdata["id"]), description=f"{host.name} adlı kullanıcının odası.")

    async def callback(self, interaction: discord.Interaction):
        id = int(self.values[0])
        room = await getroombyid(id)
        embed = discord.Embed(title=f"{id} numaralı oda")
        embed.colour = discord.Color.blurple()
        embed.description = f"**Oda Numarası**: `{id}`\n**Oda Sahibi**: {client.get_user(room['host']).name}\n**Bölüm**: {room['rundown']}\n**Katılımcılar**: {', '.join([user.mention for user in [client.get_user(user) for user in room['participants']]])}\n**Durum**: {RoomStates.fromId(room['state']).desc}\n**Başlama Tarihi**: <t:{int(room['date'].timestamp())}:R>"
        await interaction.response.send_message(embed=embed, view=RoomView(room, interaction.user.id, self.view.page), ephemeral=True)


class RightButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.blurple, label="Sonraki sayfaya git", row=2)

    async def callback(self, interaction: discord.Interaction):
        self.view.page += 1
        embed = discord.Embed(title="Odalar", colour=discord.Colour.blurple(), description="")
        rooms = await getroomsbypage(self.view.page)
        for room in rooms:
            embed.description += getRoomText(room) + "\n\n"
        embed.description = embed.description[:-2]
        embed.set_footer(text=client.user.name + " | Oda Sistemi | Sayfa " + str(self.view.page+1),
                         icon_url=client.user.avatar.url)
        count = await getcount()
        await interaction.response.edit_message(embed=embed, view=RoomSearchView(rooms, self.view.page, count // 5 + (1 if count % 5 != 0 else 0)))


class LeftButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.blurple, label="Önceki sayfaya git", row=2)

    async def callback(self, interaction: discord.Interaction):
        self.view.page -= 1
        embed = discord.Embed(title="Odalar", colour=discord.Colour.blurple(), description="")
        rooms = await getroomsbypage(self.view.page)
        for room in rooms:
            embed.description += getRoomText(room) + "\n\n"
        embed.description = embed.description[:-2]
        embed.set_footer(text=client.user.name + " | Oda Sistemi | Sayfa "+str(self.view.page+1), icon_url=client.user.avatar.url)
        count = await getcount()
        await interaction.response.edit_message(embed=embed, view=RoomSearchView(rooms, self.view.page, count // 5 + (1 if count % 5 != 0 else 0)))


class RoomSearchView(discord.ui.View):
    def __init__(self, data, page, total_page):
        super().__init__()
        self.page = page
        self.add_item(RoomSelect(data))
        if page != 0:
            self.add_item(LeftButton())
        if page != total_page-1:
            self.add_item(RightButton())


@group.command(name="ara", description="Hazır olan odalara bak")
async def oda_ara(ctx: discord.ApplicationContext):
    embed = discord.Embed(title="Odalar", colour=discord.Colour.blurple(), description="")
    rooms = await getroomsbypage(0)
    if len(rooms) != 0:
        for room in rooms:
            embed.description += getRoomText(room)+"\n\n"
        embed.description = embed.description[:-2]
        embed.set_footer(text=client.user.name + " | Oda Sistemi | Sayfa 1", icon_url=client.user.avatar.url)
        count = await getcount()
        await ctx.respond(embed=embed, view=RoomSearchView(rooms, 0, count // 5 + (1 if count % 5 else 0)), ephemeral=True)
    else:
        embed.description = "Herhangi aktif bir oda bulunmamakta"
        await ctx.respond(embed=embed, ephemeral=True)


def errorEmbed(title, desc):
    embed = discord.Embed(title=title, description=desc)
    embed.colour = discord.Color.red()
    embed.set_footer(text=client.user.name + " | Oda Sistemi", icon_url=client.user.avatar.url)
    return embed


def successEmbed(title, desc):
    embed = discord.Embed(title=title, description=desc)
    embed.colour = discord.Color.green()
    embed.set_footer(text=client.user.name + " | Oda Sistemi", icon_url=client.user.avatar.url)
    return embed


def newRoomEmbed(room):
    embed = discord.Embed(title="Yeni bir oda oluşturuldu")
    embed.colour = discord.Colour.blurple()
    embed.set_footer(text=client.user.name + " | Oda Sistemi")
    embed.description = f"**Oda Numarası**: `{room['id']}`\n**Oluşturan**: {client.get_user(room['host']).name}\n**Bölüm**: {room['rundown']}\n**Başlama Tarihi**: <t:{int(room['date'].timestamp())}:R>"
    return embed


async def getroombyid(id):
    async with client.pool.acquire() as db:
        room = await db.fetchrow("select * from rooms where id=$1", id)
        return room


async def getroomsbypage(page):
    async with client.pool.acquire() as db:
        rooms = await db.fetch(f"select * from rooms limit 5 offset {page * 5}")
        return rooms


async def getcount():
    async with client.pool.acquire() as db:
        total = await db.fetchval(f"select count(*) as total from rooms")
        return total

def getRoomText(room):
    return f"**Oda Numarası**: `{room['id']}`\n**Oda Sahibi**: {client.get_user(room['host']).name}\n**Bölüm**: {room['rundown']}\n**Katılımcılar**: **{len(room['participants'])}/4**\n**Durum**: {RoomStates.fromId(room['state']).emoji}\n**Başlama Tarihi**: <t:{int(room['date'].timestamp())}:R>"

@tasks.loop(seconds=1)
async def roomloop():
    async with client.pool.acquire() as db:
        rooms = await db.fetch("select * from rooms where state != 2")
        for room in rooms:
            now = datetime.datetime.now()
            if now.timestamp() >= room["date"].timestamp():
                await db.execute("update rooms set state=2 where id=$1", room["id"])
                users = []
                server = client.get_channel(client.logging_channel).guild
                for user in room["participants"]:
                    users.append(server.get_member(user))

                ch = await server.create_voice_channel(name="GTFO-"+str(room['id']), user_limit=4, category=server.get_channel(client.category))
                if room["lock"]:
                    await ch.set_permissions(target=server.default_role, overwrite=denyPermission)
                    for user in users:
                        await ch.set_permissions(target=user, overwrite=allowPermisson)
                invite = await ch.create_invite()

                for user in users:
                    try:
                        await user.send(embed=successEmbed("Oyun Başlıyor", f"**Oda Numarası**: `{room['id']}`\n**Oda Sahibi**: {client.get_user(room['host']).name}\n**Bölüm**: {room['rundown']}\n**Katılımcılar**: {', '.join([user.mention for user in [client.get_user(user) for user in room['participants']]])}\n**Başlama Tarihi**: <t:{int(room['date'].timestamp())}:R>\n**Link**: {invite.url}"))
                    except:
                        continue

                await client.get_channel(client.logging_channel).send(f"{', '.join([user.mention for user in users])} `{room['id']}` Numaralı Odadaki Oyununuz Başlamakta.", embed=successEmbed("Oyun Başlıyor", f"**Oda Numarası**: `{room['id']}`\n**Oda Sahibi**: {client.get_user(room['host']).name}\n**Bölüm**: {room['rundown']}\n**Katılımcılar**: {', '.join([user.mention for user in [client.get_user(user) for user in room['participants']]])}\n**Başlama Tarihi**: <t:{int(room['date'].timestamp())}:R>\n**Link**: {invite.url}"))


@tasks.loop(minutes=10)
async def killRooms():
    async with client.pool.acquire() as db:
        rooms = await db.fetch("select * from rooms where state = 2")
        for room in rooms:
            server = client.get_channel(client.logging_channel).guild
            ch = discord.utils.get(server.voice_channels, name="GTFO-"+str(room["id"]))
            diff = datetime.datetime.now().timestamp() - room["date"].timestamp()
            if diff <= 20 * 60: continue
            if len(ch.members) == 0:
                await ch.delete()
                await db.execute("delete from rooms where id=$1", room["id"])

@client.event
async def on_ready():
    print("Bot çalışıyor")
    roomloop.start()
    killRooms.start()
    await client.change_presence(activity=discord.Game(name="GTFO"), status=discord.Status.idle)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    client.pool = loop.run_until_complete(
        asyncpg.create_pool(user='postgres', password='kutup', database='gtfo', host='127.0.0.1'))
    client.run("")