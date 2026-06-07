// index.js - النسخة الجديدة بأمر !c للكباتن
const { Client, GatewayIntentBits, Events, ActionRowBuilder, StringSelectMenuBuilder } = require('discord.js');
require('dotenv').config();

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildVoiceStates
  ]
});

// ===== CONFIG =====
const allowedChannelID = "1483219896069525665"; // شات البوت
const divisionRoomID = "1475334190034587661"; // روم التقسيمة

const teamRooms = {
  1: "1483219750027919422",
  2: "151318058758478446",
  3: "ROOM_ID_3",
  4: "ROOM_ID_4",
  5: "ROOM_ID_5",
  6: "ROOM_ID_6"
};

const specialRanks = {
  capitan: "1495426762971283528",
  belt: "1490247564086214787"
};

const divisionManagerRoleID = "1475334752436359320"; // رول مسؤول التقسيمة

// ===== STATE =====
let numberOfTeams = 0;
let captains = [];
let currentCaptainTurn = 0;
let selections = {};
let waitingForCaptainMentions = false;

// ===== HELPERS =====
function canSelect(userID) {
  return userID === captains[currentCaptainTurn];
}

function getMaxSelectableForCaptain(captainId) {
  const member = client.guilds.cache.first().members.cache.get(captainId);
  if (!member) return 2;
  if (member.roles.cache.has(specialRanks.capitan) || member.roles.cache.has(specialRanks.belt)) {
    if (!selections[captainId]) return 3;
    if (selections[captainId] === 3) return 1;
    return 2;
  }
  return 2;
}

async function getPlayersInDivision(guild) {
  const channel = guild.channels.cache.get(divisionRoomID);
  if (!channel) return [];
  return channel.members ? Array.from(channel.members.values()) : [];
}

// ===== SHOW DROPDOWN =====
async function showDropdownForCaptain(captainId) {
  const channel = client.channels.cache.get(allowedChannelID);
  const captainMember = await client.guilds.cache.first().members.fetch(captainId);
  const players = await getPlayersInDivision(captainMember.guild);

  if (players.length === 0) {
    channel.send("⚠️ لا يوجد لاعبين في روم التقسيمة.");
    return;
  }

  const row = new ActionRowBuilder().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId('select_players')
      .setPlaceholder('اختر لاعبيك أو اضغط انتهاء الدور/التقسيمة')
      .addOptions([
        ...players.map(p => ({
          label: p.nickname || p.user.username,
          value: p.id
        })),
        {
          label: "✅ انتهيت من اختياراتي",
          description: "اضغط هذا الخيار لإعطاء الدور للكابتن التالي"
        },
        {
          label: "🛑 إنهاء التقسيمة",
          description: "إذا كل الكباتن اختاروا ولا يوجد لاعبين متبقين، اضغط هذا الخيار"
        }
      ])
      .setMinValues(1)
      .setMaxValues(getMaxSelectableForCaptain(captainId))
  );

  channel.send({ content: `<@${captainId}> الدور عليك! اختر لاعبيك:`, components: [row] });
}

// ===== NEXT CAPTAIN =====
function nextCaptainTurn() {
  currentCaptainTurn++;
  const channel = client.channels.cache.get(allowedChannelID);

  if (currentCaptainTurn >= captains.length) {
    channel.send("✅ اكتملت كل الاختيارات! جميع اللاعبين تم توزيعهم.");
    currentCaptainTurn = -1;
  } else {
    showDropdownForCaptain(captains[currentCaptainTurn]);
  }
}

// ===== START COMMAND =====
client.on(Events.MessageCreate, async message => {
  if (message.channel.id !== allowedChannelID) return;

  const member = await message.guild.members.fetch(message.author.id);

  // !st - بداية التقسيمة
  if (message.content.startsWith('!st')) {
    if (!member.roles.cache.has(divisionManagerRoleID)) return message.reply("❌ ليس لديك صلاحية بدء التقسيمة.");

    const row = new ActionRowBuilder().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId('select_team_count')
        .setPlaceholder('اختر عدد الفرق')
        .addOptions([
          { label: '2 فرق', value: '2' },
          { label: '4 فرق', value: '4' },
          { label: '6 فرق', value: '6' }
        ])
    );
    return message.channel.send({ content: 'اختر عدد الفرق:', components: [row] });
  }

  // !c - تسجيل الكباتن بعد اختيار عدد الفرق
  if (message.content.startsWith('!c')) {
    if (!member.roles.cache.has(divisionManagerRoleID)) return message.reply("❌ ليس لديك صلاحية تسجيل الكباتن.");
    if (!numberOfTeams) return message.reply("❌ الرجاء اختيار عدد الفرق أولاً باستخدام Dropdown.");

    // استخراج المنشنات والرقم
    const args = message.content.split(/\s+/).slice(1); // تجاهل !c
    captains = [];
    selections = {};
    currentCaptainTurn = 0;

    for (let i = 0; i < args.length; i += 2) {
      const userMention = args[i];
      const userId = userMention.replace(/[<@!>]/g, '');
      captains.push(userId);
      selections[userId] = 0;
    }

    message.channel.send(`✅ الكباتن تم تسجيلهم بالترتيب:\n${captains.map((id,i)=>`${i+1}️⃣ <@${id}>`).join("\n")}`);
    showDropdownForCaptain(captains[currentCaptainTurn]);
  }
});

// ===== INTERACTIONS =====
client.on(Events.InteractionCreate, async interaction => {
  if (!interaction.isStringSelectMenu()) return;

  if (interaction.customId === 'select_team_count') {
    numberOfTeams = parseInt(interaction.values[0]);
    return interaction.update({ content: `✅ اختر عدد الفرق: ${numberOfTeams}\nالآن استخدم الأمر !c لتسجيل الكباتن بالترتيب (مثال: !c @i39F 1 @Khaled 2)`, components: [] });
  }

  if (interaction.customId !== 'select_players') return;

  const captainId = interaction.user.id;

  if (!canSelect(captainId)) {
    return interaction.reply({ content: "الآن ليس دورك، انتظر حتى يأتي دورك.", ephemeral: true });
  }

  const selectedValues = interaction.values;

  // إنهاء التقسيمة
  if (selectedValues.includes("🛑 إنهاء التقسيمة")) {
    captains = [];
    selections = {};
    currentCaptainTurn = 0;
    return interaction.reply({ content: "🛑 تم إنهاء التقسيمة! يمكنك البدء من جديد.", ephemeral: true });
  }

  // انتهاء الدور للكابتن الحالي
  if (selectedValues.includes("✅ انتهيت من اختياراتي")) {
    nextCaptainTurn();
    return interaction.reply({ content: "✅ انتهى دورك، تم إعطاء الدور للكابتن التالي.", ephemeral: true });
  }

  // نقل اللاعبين المحددين
  const roomID = teamRooms[currentCaptainTurn + 1];
  for (const playerId of selectedValues) {
    const member = await interaction.guild.members.fetch(playerId);
    if (member.voice.channel) await member.voice.setChannel(roomID);
  }

  selections[captainId] += selectedValues.length;
  await interaction.reply({ content: "✅ تم نقل اللاعبين!", ephemeral: true });

  if (selections[captainId] >= getMaxSelectableForCaptain(captainId)) {
    nextCaptainTurn();
  }
});

client.login(process.env.DISCORD_TOKEN);
