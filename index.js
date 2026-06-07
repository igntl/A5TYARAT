require('dotenv').config();
const { Client, GatewayIntentBits, Partials, ActionRowBuilder, StringSelectMenuBuilder } = require('discord.js');

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.GuildVoiceStates],
  partials: [Partials.Channel]
});

// ===== CONFIG =====
const IDs = {
  adminRole: '1475334752436359320',
  chat: '1483219896069525665',
  voiceRoom: '1513180587584782446',
  captainRoles: ['1490247564086214787', '1495426762971283528'], // الحزام و كابيتانو
  captainVoiceRooms: [
    '1475334190034587661',
    '1483219750027919422',
    'ROOM_ID_3',
    'ROOM_ID_4',
    'ROOM_ID_5',
    'ROOM_ID_6'
  ]
};

let state = {
  numTeams: 0,
  captains: [],
  playersPool: [],
  turnIndex: 0
};

// ===== READY =====
client.once('ready', () => {
  console.log(`Logged in as ${client.user.tag}`);
});

// ===== COMMAND HANDLER =====
client.on('messageCreate', async (message) => {
  if (message.channel.id !== IDs.chat) return;
  if (!message.member.roles.cache.has(IDs.adminRole)) return;

  if (message.content === '!start') {
    state = { numTeams: 0, captains: [], playersPool: [], turnIndex: 0 };

    // Dropdown لاختيار عدد الفرق
    const row = new ActionRowBuilder().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId('select_teams')
        .setPlaceholder('اختر عدد الفرق')
        .addOptions([
          { label: '2 فرق', value: '2' },
          { label: '4 فرق', value: '4' },
          { label: '6 فرق', value: '6' }
        ])
    );
    await message.reply({ content: 'اختر عدد الفرق:', components: [row] });
  }
});

// ===== INTERACTIONS =====
client.on('interactionCreate', async (interaction) => {
  if (!interaction.isStringSelectMenu()) return;

  // اختيار عدد الفرق
  if (interaction.customId === 'select_teams') {
    state.numTeams = parseInt(interaction.values[0]);
    // جلب أعضاء روم التقسيمة
    const vcChannel = await interaction.guild.channels.fetch(IDs.voiceRoom);
    state.playersPool = vcChannel.members.map(m => m.user.username);
    await interaction.update({ content: `تم اختيار ${state.numTeams} فرق.\nاختر ${state.numTeams} كابتن بالترتيب:`, components: [] });

    // Dropdown اختيار الكباتن
    const captainOptions = state.playersPool.map(name => ({ label: name, value: name }));
    const captainRow = new ActionRowBuilder().addComponents(
      new StringSelectMenuBuilder()
        .setCustomId('select_captains')
        .setPlaceholder('اختر الكابتن الأول')
        .setMaxValues(1)
        .addOptions(captainOptions)
    );
    await interaction.followUp({ content: 'اختر الكابتن الأول:', components: [captainRow] });
  }

  // اختيار الكباتن
  if (interaction.customId === 'select_captains') {
    const chosen = interaction.values[0];
    state.captains.push(chosen);
    state.playersPool = state.playersPool.filter(p => p !== chosen);
    state.turnIndex = 0;

    if (state.captains.length < state.numTeams) {
      // Dropdown للكابتن التالي
      const nextOptions = state.playersPool.map(name => ({ label: name, value: name }));
      const captainRow = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('select_captains')
          .setPlaceholder(`اختر الكابتن ${state.captains.length + 1}`)
          .setMaxValues(1)
          .addOptions(nextOptions)
      );
      await interaction.update({ content: `تم اختيار كابتن: ${chosen}\nاختر الكابتن التالي:`, components: [captainRow] });
    } else {
      // كل الكباتن مختارين، نبدأ اختيار اللاعبين
      await interaction.update({ content: `تم اختيار جميع الكباتن: ${state.captains.join(', ')}\nبدء اختيار اللاعبين:`, components: [] });
      startPlayerPick(interaction);
    }
  }

  // اختيار اللاعبين لكل كابتن
  if (interaction.customId.startsWith('pick_player_')) {
    const captainName = interaction.customId.split('_')[2];
    const selectedPlayer = interaction.values[0];

    // نقل اللاعب تلقائيًا لروم الكابتن
    const captainIndex = state.captains.indexOf(captainName);
    const vcChannel = await interaction.guild.channels.fetch(IDs.voiceRoom);
    const member = vcChannel.members.find(m => m.user.username === selectedPlayer);
    if (member) {
      const targetRoomId = IDs.captainVoiceRooms[captainIndex];
      const targetRoom = await interaction.guild.channels.fetch(targetRoomId);
      await member.voice.setChannel(targetRoom);
    }

    // إزالة اللاعب من الباقي
    state.playersPool = state.playersPool.filter(p => p !== selectedPlayer);

    // تحديث الدور للكابتن التالي
    state.turnIndex = (state.turnIndex + 1) % state.captains.length;

    if (state.playersPool.length > 0) {
      startPlayerPick(interaction);
    } else {
      // انتهت التقسيمة
      const endRow = new ActionRowBuilder().addComponents(
        new StringSelectMenuBuilder()
          .setCustomId('end_division')
          .setPlaceholder('إنهاء التقسيمة')
          .addOptions([{ label: 'إنهاء التقسيمة', value: 'end' }])
      );
      await interaction.update({ content: 'تم اختيار جميع اللاعبين!', components: [endRow] });
    }
  }

  // إنهاء التقسيمة
  if (interaction.customId === 'end_division') {
    state = { numTeams: 0, captains: [], playersPool: [], turnIndex: 0 };
    await interaction.update({ content: 'تم إعادة تهيئة البوت للتقسيمة القادمة.', components: [] });
  }
});

// ===== FUNCTIONS =====
async function startPlayerPick(interaction) {
  const currentCaptain = state.captains[state.turnIndex];

  // Dropdown اللاعبين المتاحين
  const options = state.playersPool.map(name => ({ label: name, value: name }));
  const row = new ActionRowBuilder().addComponents(
    new StringSelectMenuBuilder()
      .setCustomId(`pick_player_${currentCaptain}`)
      .setPlaceholder(`دور ${currentCaptain} لاختيار لاعب`)
      .setMaxValues(1)
      .addOptions(options)
  );
  await interaction.followUp({ content: `دور ${currentCaptain} لاختيار لاعب:`, components: [row] });
}

// ===== LOGIN =====
client.login(process.env.DISCORD_TOKEN);
