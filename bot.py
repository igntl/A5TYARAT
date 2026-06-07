import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os

# --- إعدادات الآيديات الثابتة الحصرية لسيرفرك ---
ROLE_MANAGER_ID = 1475334752436359320       # رتبة المسؤول عن التقسيمة
ROLE_HEZAM_ID = 1490247564086214787         # رتبة الحزام
ROLE_CAPITANO_ID = 1495426762971283528      # رتبة كابيتانو

TEXT_CHANNEL_ID = 1483219896069525665       # شات البوت الكتابي المسموح به
LOBBY_VOICE_ID = 1475334190034587661        # روم التقسيمة الصوتي (التجمع)

# رومات الكباتن بالترتيب الدقيق من 1 إلى 6
TEAM_CHANNELS = [
    1483219750027919422,  # روم الكابتن 1
    1513180587584782446,  # روم الكابتن 2
    0,                    # روم الكابتن 3 (استبدل الـ 0 بالآيدي)
    0,                    # روم الكابتن 4 (استبدل الـ 0 بالآيدي)
    0,                    # روم الكابتن 5 (استبدل الـ 0 بالآيدي)
    0                     # روم الكابتن 6 (استبدل الـ 0 بالآيدي)
]

# --- إعدادات البوت ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

class ProClubBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        await self.tree.sync()
        print("⚽ تم تشغيل بوت البرو كلوب ومزامنة الأوامر بنجاح!")

bot = ProClubBot()
session = {} # ذاكرة الجلسة الحالية للتقسيمة

# --- دالة مساعدة لتقسيم القوائم إلى صفحات (بسبب حد ديسكورد 25 خيار) ---
def get_page_options(members_list, page=0, per_page=23):
    start = page * per_page
    end = start + per_page
    sub_list = members_list[start:end]
    
    options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in sub_list]
    
    # إضافة خيارات التنقل بين الصفحات إذا كانت القائمة أكبر من الصفحة الحالية
    if page > 0:
        options.insert(0, discord.SelectOption(label="⬅️ الصفحة السابقة", value="prev_page"))
    if end < len(members_list):
        options.append(discord.SelectOption(label="➡️ الصفحة التالية", value="next_page"))
        
    if not options:
        options.append(discord.SelectOption(label="لا يوجد لاعبين متاحين بروم التجمع", value="none"))
    return options

# --- 1. واجهة اختيار عدد الفرق ---
class TeamCountSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="فريقين (2)", value="2"),
            discord.SelectOption(label="4 فرق (4)", value="4"),
            discord.SelectOption(label="6 فرق (6)", value="6")
        ]
        super().__init__(placeholder="اختر عدد الفرق المطلوبة للتقسيمة...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الخيار مخصص للمسؤولين فقط.", ephemeral=True)
            return
            
        session["teams_count"] = int(self.values[0])
        session["captains"] = []
        session["current_cap_setup_index"] = 1
        
        await interaction.response.defer()
        # الانتقال فوراً للمرحلة التالية: اختيار الكباتن
        await update_captain_setup_message(interaction)

class TeamCountView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TeamCountSelect())

# --- 2. واجهة اختيار الكباتن بالترتيب حبة حبة حبة ---
class CaptainSelect(discord.ui.Select):
    def __init__(self, lobby_members, page=0):
        self.page = page
        self.lobby_members = lobby_members
        options = get_page_options(lobby_members, page)
        super().__init__(placeholder=f"اختر الكابتن رقم {session['current_cap_setup_index']} بالترتيب...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الخيار مخصص للمسؤولين فقط.", ephemeral=True)
            return

        val = self.values[0]
        if val == "next_page":
            await interaction.response.edit_message(view=CaptainSetupView(self.lobby_members, self.page + 1))
            return
        elif val == "prev_page":
            await interaction.response.edit_message(view=CaptainSetupView(self.lobby_members, self.page - 1))
            return
        elif val == "none":
            return

        cap_id = int(val)
        if cap_id in session["captains"]:
            await interaction.response.send_message("هذا العضو تم اختياره كابتن بالفعل! اختر شخصاً آخر.", ephemeral=True)
            return

        session["captains"].append(cap_id)
        session["current_cap_setup_index"] += 1
        
        await interaction.response.defer()
        await update_captain_setup_message(interaction)

class CaptainSetupView(discord.ui.View):
    def __init__(self, lobby_members, page=0):
        super().__init__(timeout=None)
        self.add_item(CaptainSelect(lobby_members, page))

async def update_captain_setup_message(interaction: discord.Interaction):
    guild = interaction.guild
    lobby_channel = guild.get_channel(LOBBY_VOICE_ID)
    
    if not lobby_channel:
        await interaction.followup.send("❌ خطأ: تعذر العثور على روم التقسيمة الصوتي.")
        return

    # استبعاد الذين تم اختيارهم ككباتن بالفعل من القائمة لتسهيل العمل
    available_members = [m for m in lobby_channel.members if m.id not in session["captains"]]

    if session["current_cap_setup_index"] <= session["teams_count"]:
        embed = discord.Embed(
            title="🏃‍♂️ مرحلة تحديد كباتن الفرق",
            description=f"الرجاء من المسؤول اختيار **الكابتن رقم {session['current_cap_setup_index']}** من القائمة المنسدلة بالأسفل بالترتيب.\n\n"
                        f"*الأسماء تظهر بالنك نيم المباشر المتواجدين داخل روم التقسيمة حالياً.*",
            color=discord.Color.orange()
        )
        await interaction.message.edit(embed=embed, view=CaptainSetupView(available_members))
    else:
        # انتهى اختيار الكباتن بالكامل -> نبدأ الدرفت الفعلي فوراً
        session["players_pool"] = [m.id for m in lobby_channel.members if m.id not in session["captains"]]
        session["current_captain_index"] = 0
        session["round_number"] = 1  # تتبع الجولات لحساب الرتب الخاصة
        session["event"] = asyncio.Event()
        
        bot.loop.create_task(run_draft_engine(interaction))

# --- 3. واجهة اختيار اللاعبين للكباتن (The Draft) ---
class PlayerSelectMenu(discord.ui.Select):
    def __init__(self, lobby_members, max_values=1, page=0):
        self.page = page
        self.lobby_members = lobby_members
        self.max_values = max_values
        options = get_page_options(lobby_members, page)
        super().__init__(
            placeholder="اختر اللاعبين لنقلهم إلى رومك الصوتي...",
            min_values=1,
            max_values=min(max_values, len(options)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        expected_captain = session["captains"][session["current_captain_index"]]
        if interaction.user.id != expected_captain:
            await interaction.response.send_message("❌ ليس دورك في الاختيار الآن! انتظر دورك المخصص.", ephemeral=True)
            return

        val = self.values[0]
        if val == "next_page":
            await interaction.response.edit_message(view=PlayerDraftView(self.lobby_members, self.max_values, self.page + 1))
            return
        elif val == "prev_page":
            await interaction.response.edit_message(view=PlayerDraftView(self.lobby_members, self.max_values, self.page - 1))
            return
        elif val == "none":
            return

        await interaction.response.defer()
        
        selected_ids = [int(v) for v in self.values if v not in ["next_page", "prev_page"]]
        target_voice_id = TEAM_CHANNELS[session["current_captain_index"]]
        target_voice_channel = interaction.guild.get_channel(target_voice_id)

        # سحب اللاعبين المختارين فورا إلى روم الكابتن المحدد
        if target_voice_channel:
            for p_id in selected_ids:
                if p_id in session["players_pool"]:
                    session["players_pool"].remove(p_id)
                    member = interaction.guild.get_member(p_id)
                    if member and member.voice and member.voice.channel:
                        try:
                            await member.move_to(target_voice_channel)
                        except:
                            pass

        # نقل الدور للكابتن التالي
        session["current_captain_index"] += 1
        if session["current_captain_index"] >= len(session["captains"]):
            session["current_captain_index"] = 0
            session["round_number"] += 1 # الانتقال للجولة التالية لجميع الكباتن
            
        session["event"].set()

class PlayerDraftView(discord.ui.View):
    def __init__(self, lobby_members, max_values=1, page=0):
        super().__init__(timeout=40)
        self.add_item(PlayerSelectMenu(lobby_members, max_values, page))

# --- 4. واجهة إنهاء وإعادة تهيئة التقسيمة ---
class ResetSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label="🏁 إنهاء التقسيمة وإعادة التهيئة", value="reset_all")]
        super().__init__(placeholder="خيارات المسؤول لإغلاق وإعادة تهيئة البوت...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
            await interaction.response.send_message("❌ هذا الخيار مخصص للمسؤولين فقط.", ephemeral=True)
            return
            
        session.clear()
        embed = discord.Embed(
            title="🏁 تم إنهاء التقسيمة",
            description="تمت إعادة تهيئة البوت بالكامل بنجاح وهو جاهز الآن لاستقبال تقسيمة جديدة في أي وقت باستخدام الأمر `/تقسيم`.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class ResetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ResetSelect())

# --- محرك إدارة جولات التقسيم الذكي الصارم ---
async def run_draft_engine(interaction: discord.Interaction):
    guild = interaction.guild
    channel = interaction.channel

    while session["players_pool"]:
        # تحديث قائمة المتواجدين فعلياً بروم التجمع باستمرار لمنع المشاكل وفلترة الخارجين
        lobby_channel = guild.get_channel(LOBBY_VOICE_ID)
        current_lobby_ids = [m.id for m in lobby_channel.members] if lobby_channel else []
        session["players_pool"] = [p for p in session["players_pool"] if p in current_lobby_ids]

        if not session["players_pool"]:
            break

        idx = session["current_captain_index"]
        cap_id = session["captains"][idx]
        captain_member = guild.get_member(cap_id)

        if not captain_member:
            session["current_captain_index"] += 1
            if session["current_captain_index"] >= len(session["captains"]):
                session["current_captain_index"] = 0
                session["round_number"] += 1
            continue

        # حساب الصلاحيات والحصص الخاصة بالرتب (الحزام أو كابيتانو) بدقة تامة:
        # الدور الأول (الجولة 1): 3 لاعبين | الدور التالي (الجولة 2): شخص واحد | الجولات اللاحقة (3+): شخصين 2
        has_special_role = any(r.id in [ROLE_HEZAM_ID, ROLE_CAPITANO_ID] for r in captain_member.roles)
        
        if has_special_role:
            if session["round_number"] == 1:
                max_pick = 3
            elif session["round_number"] == 2:
                max_pick = 1
            else:
                max_pick = 2
        else:
            max_pick = 1 # الكابتن العادي يختار لاعب واحد دائماً في كل جولة

        session["event"] = asyncio.Event()
        
        # جلب قائمة الأعضاء المتاحين حالياً بالنك نيم فقط
        available_members = [guild.get_member(p_id) for p_id in session["players_pool"] if guild.get_member(p_id) is not None]

        view = PlayerDraftView(available_members, max_values=max_pick)
        
        embed = discord.Embed(
            title=f"📋 جولة الاختيار رقم {session['round_number']}",
            description=f"الدور الآن عند الكابتن: {captain_member.mention}\n"
                        f"يرجى فتح القائمة بالأسفل واختيار لاعبيك. لديك **30 ثانية** فقط.\n\n"
                        f"⚡ حصتك المتاحة في هذا الدور: **{max_pick} لاعبين** دفعة واحدة.",
            color=discord.Color.blue()
        )
        
        draft_msg = await channel.send(embed=embed, view=view)

        # تايمر الـ 30 ثانية لإنهاء التأخير بشكل كامل
        try:
            await asyncio.wait_for(session["event"].wait(), timeout=30.0)
        except asyncio.TimeoutError:
            # الاختيار التلقائي السريع إذا تأخر الكابتن
            if session["players_pool"]:
                import random
                auto_picks = random.sample(session["players_pool"], min(max_pick, len(session["players_pool"])))
                target_voice_id = TEAM_CHANNELS[idx]
                target_voice_channel = guild.get_channel(target_voice_id)
                
                if target_voice_channel:
                    for p_id in auto_picks:
                        if p_id in session["players_pool"]:
                            session["players_pool"].remove(p_id)
                            member = guild.get_member(p_id)
                            if member and member.voice and member.voice.channel:
                                try:
                                    await member.move_to(target_voice_channel)
                                except:
                                    pass
                await channel.send(f"⏱️ **انتهى الوقت!** قام البوت بسحب لاعبين عشوائيين لـ {captain_member.mention} لضمان سرعة السهرة.")
            
            # الانتقال التلقائي للكابتن القادم
            session["current_captain_index"] += 1
            if session["current_captain_index"] >= len(session["captains"]):
                session["current_captain_index"] = 0
                session["round_number"] += 1

        try:
            await draft_msg.delete()
        except:
            pass

    # انتهاء كل اللاعبين وظهور زر إعادة التهيئة للمسؤول
    embed_end = discord.Embed(
        title="🎉 تم توزيع جميع اللاعبين بنجاح!",
        description="انتهت عملية التقسيم بالكامل وبسرعة قياسية، يتوجب على المسؤول الآن الضغط بالأسفل لإعادة تهيئة البوت للتقسيمات القادمة.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed_end, view=ResetView())

# --- الأمر المائل الحصري للمشرف المكتوب بشات محدد ---
@bot.tree.command(name="تقسيم", description="بدء العملية التفاعلية المتكاملة لتقسيم لاعبي البرو كلوب")
async def تقسيم(interaction: discord.Interaction):
    # 1. التحقق من صلاحية رتبة مسؤول التقسيمة
    if not any(r.id == ROLE_MANAGER_ID for r in interaction.user.roles):
        await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص فقط لمن يحمل رتبة المسؤول عن التقسيمة!", ephemeral=True)
        return

    # 2. التحقق من كتابة الأمر في الشات الصحيح المحدد بالآيدي
    if interaction.channel_id != TEXT_CHANNEL_ID:
        await interaction.response.send_message(f"❌ هذا الأمر يمكن تشغيله فقط داخل شات البوت المخصص: <#{TEXT_CHANNEL_ID}>", ephemeral=True)
        return

    # 3. التحقق من تواجد لاعبين داخل روم التقسيمة الصوتي
    lobby_channel = interaction.guild.get_channel(LOBBY_VOICE_ID)
    if not lobby_channel or not lobby_channel.members:
        await interaction.response.send_message("❌ روم التقسيمة الصوتي فارغ حالياً! يجب دخول اللاعبين أولاً لبدء العملية.", ephemeral=True)
        return

    session.clear() # تصفية أي جلسة معلقة قديمة
    
    embed = discord.Embed(
        title="⚽ بدء تقسيمة الفيفا برو كلوب ⚽",
        description="أهلاً بك يا مسؤول، يرجى تحديد عدد الفرق المطلوبة لهذه السهرة من القائمة بالأسفل للانتقال لتحديد الكباتن:",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, view=TeamCountView())

# تشغيل البوت المتوافق مع متطلبات ريلوي وبيئة DISCORD_TOKEN المحمية
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Error: DISCORD_TOKEN variable not found in Railway Settings.")
