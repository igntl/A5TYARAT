// index.js - النسخة النهائية العملية
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
let remainingPlayers = [];

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

async function showDropdownForCaptain(captainId) {
  const channel = client.channels.cache.get(allowedChannelID);
  const captainMember = await client.guilds.cache.first().members.fetch(captainId);

  if (remainingPlayers.length === 0) {
    channel.send("⚠️ لا يوجد لاعبين متبقين للاختيار.");
    return;
  }

  const row = new ActionRowBuilder().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId('select_players')
      .setPlaceholder('اختر لاعبيك أو إنهاء الدور/التقسيمة')
      .addOptions([
        ...remainingPlayers.map(p => ({
          label: p.nickname || p.user.username,
          value: p.id
        })),
        { label: "✅ انتهيت من اختياراتي", description: "اعط الدور للكابتن التالي" },
        { label: "🛑 إنهاء التقسيمة", description: "انتهت كل الاختيارات" }
      ])
      .setMinValues(1)
      .setMaxValues(getMaxSelectableForCaptain(captainId))
  );

  channel.send({ content: `<@${captainId}> الدور عليك! اختر لاعبيك:`, components: [row] });
}

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

// ===== START COMMAND !st =====
client.on(Events.MessageCreate, async message => {
  if (message.channel.id !== allowedChannelID) return;
  if (!message.content.startsWith('!st')) return;

  const member = await message.guild.members.fetch(message.author.id);
  if (!member.roles.cache.has(divisionManagerRoleID)) {
    return message.reply("❌ ليس لديك صلاحية بدء التقسيمة.");
  }

  const args = message.content.split(/\s+/).slice(1); // !st [عدد الفرق] [@c1 1 ...]
  if (!args.length) return message.reply("❌ الرجاء تحديد عدد الفرق والكباتن مع المنشن بعد !st");

  numberOfTeams = parseInt(args[0]);
  if (![2,4,6].includes(numberOfTeams)) return message.reply("❌ عدد الفرق يجب أن يكون 2، 4 أو 6.");

  captains = [];
  selections = {};
  currentCaptainTurn = 0;

  for (let i = 1; i < args.length; i += 2) {
    const mention = args[i];
    const userId = mention.replace(/[<@!>]/g, '');
    captains.push(userId);
    selections[userId] = 0;
  }

  const allMembers = await getPlayersInDivision(message.guild);
  remainingPlayers = allMembers.filter(m => !captains.includes(m.id));

  message.channel.send(`✅ تم تسجيل الكباتن بالترتيب:\n${captains.map((id,i)=>`${i+1}️⃣ <@${id}>`).join("\n")}`);
  showDropdownForCaptain(captains[currentCaptainTurn]);
});

// ===== INTERACTIONS =====
client.on(Events.InteractionCreate, async interaction => {
  if (!interaction.isStringSelectMenu()) return;

  if (interaction.customId !== 'select_players') return;

  const captainId = interaction.user.id;
  if (!canSelect(captainId)) return interaction.reply({ content: "الآن ليس دورك.", ephemeral: true });

  const selectedValues = interaction.values;

  if (selectedValues.includes("🛑 إنهاء التقسيمة")) {
    captains = [];
    selections = {};
    currentCaptainTurn = 0;
    remainingPlayers = [];
    return interaction.reply({ content: "🛑 تم إنهاء التقسيمة! يمكنك البدء من جديد.", ephemeral: true });
  }

  if (selectedValues.includes("✅ انتهيت من اختياراتي")) {
    nextCaptainTurn();
    return interaction.reply({ content: "✅ انتهى دورك، تم إعطاء الدور للكابتن التالي.", ephemeral: true });
  }

  // نقل اللاعبين المحددين
  const roomID = teamRooms[currentCaptainTurn + 1];
  for (const playerId of selectedValues) {
    const member = await interaction.guild.members.fetch(playerId);
    if (member.voice.channel) await member.voice.setChannel(roomID);
    remainingPlayers = remainingPlayers.filter(p => p.id !== playerId);
  }

  selections[captainId] += selectedValues.length;
  await interaction.reply({ content: "✅ تم نقل اللاعبين!", ephemeral: true });

  if (selections[captainId] >= getMaxSelectableForCaptain(captainId)) {
    nextCaptainTurn();
  }
});

client.login(process.env.DISCORD_TOKEN);
