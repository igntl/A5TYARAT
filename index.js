// index.js
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
const allowedChannelID = "1483219896069525665"; // الشات المسموح للبوت
const divisionRoomID = "1475334190034587661"; // روم التقسيمة

const teamRooms = {
  1: "1483219750027919422",
  2: "1513180587584782446",
  3: "ROOM_ID_3",
  4: "ROOM_ID_4",
  5: "ROOM_ID_5",
  6: "ROOM_ID_6"
};

const specialRanks = {
  capitan: "1495426762971283528",
  belt: "1490247564086214787"
};

// ===== STATE =====
let numberOfTeams = 0;
let captains = [];
let currentCaptainTurn = 0;
let selections = {};

// ===== HELPERS =====
function isCaptain(userID) {
  return captains.includes(userID);
}

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

// ===== UTILITY FUNCTIONS =====
async function getPlayersInDivision(guild) {
  const channel = guild.channels.cache.get(divisionRoomID);
  if (!channel) return [];
  return channel.members ? Array.from(channel.members.values()) : [];
}

async function showDropdownForCaptain(captainId, channel) {
  const captainMember = await client.guilds.cache.first().members.fetch(captainId);
  const players = await getPlayersInDivision(captainMember.guild);

  if (players.length === 0) {
    channel.send("⚠️ لا يوجد لاعبين في روم التقسيمة.");
    return;
  }

  const row = new ActionRowBuilder().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId('select_players')
      .setPlaceholder('اختر لاعبيك أو اختر إنهاء التقسيمة')
      .addOptions([
        ...players.map(p => ({
          label: p.nickname || p.user.username,
          value: p.id
        })),
        {
          label: "🛑 إنهاء التقسيمة",
          description: "إذا كل الكباتن اختاروا لاعبيهم ولم يبقى لاعبين، اضغط هذا الخيار",
          value: "END_DIVISION"
        }
      ])
      .setMinValues(1)
      .setMaxValues(getMaxSelectableForCaptain(captainId))
  );

  channel.send({ content: `<@${captainId}> الدور عليك! اختر لاعبيك:`, components: [row] });
}

async function nextCaptainTurn(channel) {
  currentCaptainTurn++;
  if (currentCaptainTurn >= captains.length) {
    channel.send("✅ اكتملت كل الاختيارات! جميع اللاعبين تم توزيعهم.");
    currentCaptainTurn = -1;
  } else {
    showDropdownForCaptain(captains[currentCaptainTurn], channel);
  }
}

// ===== COMMANDS =====
client.on(Events.MessageCreate, async (message) => {
  if (message.channel.id !== allowedChannelID) return;
  if (!message.content.startsWith('!')) return;

  const args = message.content.split(/\s+/);
  const command = args[0];

  if (command === '!f') {
    const num = parseInt(args[1]);
    if (!num || num < 2 || num > 6) return message.reply("عدد الفرق يجب أن يكون بين 2 و 6.");
    numberOfTeams = num;
    return message.reply(`✅ تم تحديد عدد الفرق: ${numberOfTeams}`);
  }

  if (command === '!c') {
    if (!numberOfTeams) return message.reply("حدد عدد الفرق أولاً بـ !f");
    if ((args.length -1)/2 < numberOfTeams) return message.reply("حدد الكباتن مع أرقام ترتيبهم.");

    captains = [];
    selections = {};
    currentCaptainTurn = 0;

    for (let i = 1; i < args.length; i += 2) {
      const mention = args[i];
      const num = parseInt(args[i+1]);
      if (!mention.startsWith('<@') || !num) continue;
      const id = mention.replace(/\D/g,'');
      captains[num -1] = id;
      selections[id] = 0;
    }

    showDropdownForCaptain(captains[currentCaptainTurn], message.channel);
  }
});

// ===== INTERACTIONS =====
client.on(Events.InteractionCreate, async interaction => {
  if (!interaction.isStringSelectMenu()) return;
  if (interaction.customId !== 'select_players') return;

  const captainId = interaction.user.id;

  if (!canSelect(captainId)) {
    return interaction.reply({ content: "الآن ليس دورك، انتظر حتى يأتي دورك.", ephemeral: true });
  }

  const selectedPlayers = interaction.values;

  // التحقق إذا اختار إنهاء التقسيمة
  if (selectedPlayers.includes("END_DIVISION")) {
    captains = [];
    selections = {};
    currentCaptainTurn = 0;
    return interaction.reply({ content: "🛑 تم إنهاء التقسيمة! يمكنك البدء من جديد.", ephemeral: true });
  }

  const roomID = teamRooms[currentCaptainTurn + 1];

  for (const playerId of selectedPlayers) {
    const member = await interaction.guild.members.fetch(playerId);
    if (member.voice.channel) await member.voice.setChannel(roomID);
  }

  selections[captainId] += selectedPlayers.length;
  await interaction.reply({ content: "✅ تم نقل اللاعبين!", ephemeral: true });

  if (selections[captainId] >= getMaxSelectableForCaptain(captainId)) {
    nextCaptainTurn(interaction.channel);
  }
});

client.login(process.env.DISCORD_TOKEN);
