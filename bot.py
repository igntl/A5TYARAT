import discord
from discord.ext import commands
from discord import app_commands
import os

ROLE_MANAGER_ID = 1360011347768774796       
ROLE_HEZAM_ID = 1496134224795799592         
ROLE_CAPITANO_ID = 1487063117375602819      

TEXT_CHANNEL_ID = 1523913284351426742       
LOBBY_VOICE_ID = 1359226687216418856        

TEAM_CHANNELS = [
    1359280052109443173, 
    1359280380599079022, 
    1359280446952833095, 
    1359280489923477754, 
    1359280772707651684, 
    1359280733650288723, 
    1494687589616320654, 
    1494687636273762546   
]

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

class NewProClubBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print("Bot is ready")

bot = NewProClubBot()

session = {
    "active": False,
    "captains": [],
    "round": 1,
    "current_index": 0,
    "custom_picks_r1": {},  
    "custom_picks_r2": {},
    "setup_manager": None,
    "setup_index": 0,
    "setup_round": 1
}

def get_all_available_members(guild):
    lobby_channel = guild.get_channel(LOBBY_VOICE_ID)
    if not lobby_channel:
        return []
    return [m for m in lobby_channel.members if m.id not in session["captains"] and not m.bot]

class SetupMenu(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 6)]
        super().__init__(placeholder="حدد عدد الاختيارات...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != session["setup_manager"]:
            await interaction.response.send_message("الامر مخصص للمسؤول فقط", ephemeral=True)
            return
        
        val = int(self.values[0])
        cap_id = session["captains"][session["setup_index"]]
        guild = interaction.guild
        
        if session["setup_round"] == 1:
            session["custom_picks_r1"][cap_id] = val
            session["setup_round"] = 2
            
            captain_member = guild.get_member(cap_id)
            name = captain_member.display_name if captain_member else f"الكابتن {session['setup_index'] + 1}"
            content = f"حدد عدد اختيارات {name} في اللفة الثانية:"
            await interaction.response.edit_message(content=content, view=SetupView())
        else:
            session["custom_picks_r2"][cap_id] = val
            session["setup_index"] += 1
            session["setup_round"] = 1
            
            if session["setup_index"] < len(session["captains"]):
                next_cap_id = session["captains"][session["setup_index"]]
                captain_member = guild.get_member(next_cap_id)
                name = captain_member.display_name if captain_member else f"الكابتن {session['setup_index'] + 1}"
                content = f"حدد عدد اختيارات {name} في اللفة الاولى:"
                await interaction.response.edit_message(content=content, view=SetupView())
            else:
                session["active"] = True
                session["current_index"] = 0
                session["round"] = 1
                
                await interaction.response.edit_message(content="تم حفظ جميع الاختيارات وتبدأ التقسيمة الان", view=None)
                await send_next_turn(interaction.channel, guild)

class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SetupMenu())

class MultiDraftMenu(discord.ui.Select):
    def __init__(self, placeholder, options, max_picks):
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=min(max_picks, len(options)),
            options=options
        )
        self.max_picks = max_picks

    async def callback(self, interaction: discord.Interaction):
        if not session["active"]:
            await interaction.response.send_message("لا توجد تقسيمة نشطة حاليا", ephemeral=True)
            return
        current_cap_id = session["captains"][session["current_index"]]
        if interaction.user.id != current_cap_id:
            await interaction.response.send_message("ليس دورك في الاختيار الان انتظر منشن البوت", ephemeral=True)
            return

        selected_members = [int(v) for v in self.values]
        lobby_channel = interaction.guild.get_channel(LOBBY_VOICE_ID)
        current_lobby_ids = [m.id for m in lobby_channel.members] if lobby_channel else []

        missing_players = [p_id for p_id in selected_members if p_id not in current_lobby_ids]
        if missing_players:
            await interaction.response.send_message("خرج بعض اللاعبين الذين اخترتهم من الروم الصوتي، يرجى إعادة المحاولة من القائمة المحدثة.", ephemeral=True)
            return

        await interaction.response.defer()
        target_room_id = TEAM_CHANNELS[session["current_index"]]
        target_room = interaction.guild.get_channel(target_room_id)
        
        for p_id in selected_members:
            member = interaction.guild.get_member(p_id)
            if member and member.voice and member.voice.channel:
                try:
                    await member.move_to(target_room)
                except:
                    pass

        session["current_index"] += 1
        if session["current_index"] >= len(session["captains"]):
            session["current_index"] = 0
            session["round"] += 1

        try:
            await interaction.message.delete()
        except:
            pass
        await send_next_turn(interaction.channel, interaction.guild)

class MultiDraftView(discord.ui.View):
    def __init__(self, available_members, max_picks):
        super().__init__(timeout=None)
        
        # تقسيم اللاعبين المتاحين إلى مجموعات، كل مجموعة بحد أقصى 25 اسم
        chunk_size = 25
        chunks = [available_members[i:i + chunk_size] for i in range(0, len(available_members), chunk_size)]
        
        for index, chunk in enumerate(chunks):
            options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in chunk]
            start_num = (index * chunk_size) + 1
            end_num = start_num + len(chunk) - 1
            placeholder = f"قائمة اللاعبين من {start_num} إلى {end_num}"
            self.add_item(MultiDraftMenu(placeholder, options, max_picks))

class ResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="إنهاء التقسيمة", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("هذا الخيار مخصص للمسؤولين فقط", ephemeral=True)
            return
        session["active"] = False
        session["captains"] = []
        session["round"] = 1
        session["current_index"] = 0
        session["custom_picks_r1"] = {}
        session["custom_picks_r2"] = {}
        await interaction.response.edit_message(content="تم إنهاء التقسيمة وتصفير البوت بنجاح جاهز للتقسيمة القادمة", embed=None, view=None)

class ResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ResetButton())

def get_current_max_picks(captain_id):
    if session["round"] == 1:
        return session["custom_picks_r1"].get(captain_id, 2)
    elif session["round"] == 2:
        return session["custom_picks_r2"].get(captain_id, 2)
    else:
        return 2

async def send_next_turn(channel, guild):
    actual_available = get_all_available_members(guild)
    
    if session["round"] > 1 and not actual_available:
        embed = discord.Embed(
            title="تم توزيع جميع اللاعبين بنجاح",
            description="انتهت عملية التقسيمة بالكامل يتوجب على المسؤول الضغط على الزر بالاسفل لتصفير البوت",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=ResetView())
        return

    cap_id = session["captains"][session["current_index"]]
    captain_member = guild.get_member(cap_id)
    
    if not captain_member:
        session["current_index"] += 1
        if session["current_index"] >= len(session["captains"]):
            session["current_index"] = 0
            session["round"] += 1
        await send_next_turn(channel, guild)
        return

    picks_allowed = get_current_max_picks(cap_id)
    embed = discord.Embed(
        title=f"جولة الاختيار رقم {session['round']}",
        description=f"الدور الان عندك يا كابتن: {captain_member.mention}\nالرجاء اختيار لاعبيك من القوائم بالاسفل\n\nاختياراتك المتاحة في هذا الدور: {picks_allowed} لاعبين دفعة واحدة",
        color=discord.Color.blue()
    )
    
    # إرسال الرسالة مع دعم القوائم المتعددة التلقائية بناءً على عدد الحضور
    if not actual_available:
        # قائمة وهمية فارغة في حال عدم وجود أحد لمنع الكراش عند البدء المفاجئ
        options = [discord.SelectOption(label="لا يوجد لاعبين متاحين حاليا بروم التجمع", value="none")]
        view = discord.ui.View()
        view.add_item(discord.ui.Select(placeholder="القائمة فارغة...", options=options, disabled=True))
        await channel.send(content=captain_member.mention, embed=embed, view=view)
    else:
        await channel.send(content=captain_member.mention, embed=embed, view=MultiDraftView(actual_available, picks_allowed))

@bot.tree.command(name="تقسيم", description="بدء التقسيم وتحديد اختيارات كل كابتن")
@app_commands.describe(
    عدد_الفرق="اختر عدد الفرق المشاركة (2، 4، 6، أو 8)",
    كابتن_1="الكابتن 1", كابتن_2="الكابتن 2", كابتن_3="الكابتن 3", كابتن_4="الكابتن 4",
    كابتن_5="الكابتن 5", كابتن_6="الكابتن 6", كابتن_7="الكابتن 7", كابتن_8="الكابتن 8"
)
async def تقسيم(
    interaction: discord.Interaction, عدد_الفرق: int, 
    كابتن_1: discord.Member, كابتن_2: discord.Member, 
    كابتن_3: discord.Member = None, كابتن_4: discord.Member = None, 
    كابتن_5: discord.Member = None, كابتن_6: discord.Member = None, 
    كابتن_7: discord.Member = None, كابتن_8: discord.Member = None
):
    if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
        await interaction.response.send_message("عذرا هذا الأمر مخصص فقط لمن يحمل رتبة المسؤول عن التقسيمة", ephemeral=True)
        return

    if interaction.channel_id != TEXT_CHANNEL_ID:
        await interaction.response.send_message(f"هذا الأمر يعمل فقط داخل شات البوت المخصص: <#{TEXT_CHANNEL_ID}>", ephemeral=True)
        return

    if عدد_الفرق not in [2, 4, 6, 8]:
        await interaction.response.send_message("الرجاء اختيار عدد فرق صحيح (2 أو 4 أو 6 أو 8 فقط)", ephemeral=True)
        return

    all_caps = [كابتن_1, كابتن_2, كابتن_3, كابتن_4, كابتن_5, كابتن_6, كابتن_7, كابتن_8]
    chosen_caps = [c.id for c in all_caps[:عدد_الفرق] if c is not None]

    if len(chosen_caps) != عدد_الفرق:
        await interaction.response.send_message(f"خطأ: اخترت {عدد_الفرق} فرق ولكن لم تقم بمنشنة كباتن كافيين بالتوالي", ephemeral=True)
        return

    session["active"] = False
    session["captains"] = chosen_caps
    session["custom_picks_r1"] = {}
    session["custom_picks_r2"] = {}
    session["setup_manager"] = interaction.user.id
    session["setup_index"] = 0
    session["setup_round"] = 1

    captain_member = interaction.guild.get_member(chosen_caps[0])
    name = captain_member.display_name if captain_member else "الكابتن 1"
    
    await interaction.response.send_message(f"حدد عدد اختيارات {name} في اللفة الاولى:", view=SetupView())

@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("تم تحديث ومزامنة البوت بنجاح")

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Error: DISCORD_TOKEN is missing.")
