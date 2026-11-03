"""Andy's other languages: what's written by hand for each, so that no model ever writes it.

For people who live at home in the language they grew up with: in the US, the grandparent who speaks Mandarin,
Tagalog, Vietnamese, Korean or Russian. Omnilingual ASR (Meta's) hears each, SeamlessM4T v2 (Meta's) speaks each,
and Muse Glimmer on this computer translates in between (companion/language.py), so the person's words never leave
the house for it. Chosen from the languages SeamlessM4T v2 can speak, among those most spoken at home in the US.

Written here, by hand, never by a model at runtime:
- saying Andy is an AI, and the crisis reply. 988 has interpreters by phone (LanguageLine, 240+ languages); its text
  and chat are English and Spanish only, so the reply says to call and ask for an interpreter;
- Andy's short lines ("Let me look.", "There they are!"), which a translator gets wrong without context, and which
  avoid the thing's grammatical gender (Andy doesn't know if it's "le" or "la");
- everyday things, for the TV's labels;
- one worked example each way, used only when a translation comes back unchanged.
A native speaker should read each language's lines before a home relies on them (docs/research.md, 54).
The crisis words themselves are in companion/safety.py, beside the English and Spanish.
"""

# The short lines, in this order, for each language (app.FOUND_OPENERS and the search's first words)
LINES = ["Let me look.", "Let me look around the room.", "Let me see.", "Okay.", "Yes?", "Stopped.", "There it is!",
         "There they are!", "Found it!", "Found them!", "Ah, there it is!", "Ah, there they are!"]
THINGS = ["keys", "glasses", "phone", "remote", "wallet", "mug", "cup", "watch", "bag", "book", "bottle", "umbrella"]
TO_EN = "remind me at 9 am to water the plants"  # each language's worked example into English
FROM_EN = "I'll remind you at 5 PM to call your daughter."  # and out of it

# code: (English name, its own name, Omnilingual ASR code, SeamlessM4T v2 voice, "on this computer", "Okay, I'll
#        speak it now.", "I'm Andy, an AI robot.", the crisis reply, LINES, THINGS, TO_EN, FROM_EN)
MORE = {
    "zh": ("Chinese", "中文", "cmn_Hans", "cmn", "在这台电脑上", "好的，现在我说中文。", "我是 Andy，一个人工智能机器人。",
           "我是机器人，没办法像人那样帮您。您可以随时拨打 988 危机生命线，白天晚上都可以，并说您需要中文口译员。"
           "如果您现在有危险，请拨打 911。",
           ["我来找找。", "我在房间里找找。", "我看看。", "好的。", "您说？", "好，停下了。", "在那儿！", "在那儿！", "找到了！",
            "找到了！", "啊，在那儿！", "啊，在那儿！"],
           ["钥匙", "眼镜", "手机", "遥控器", "钱包", "马克杯", "杯子", "手表", "包", "书", "瓶子", "雨伞"],
           "早上九点提醒我给花浇水", "下午5点我会提醒您给女儿打电话。"),
    "tl": ("Tagalog", "Tagalog", "tgl_Latn", "tgl", "sa computer na ito", "Sige po, magta-Tagalog na ako ngayon.",
           "Ako si Andy, isang AI na robot.",
           "Robot ako, kaya hindi kita matutulungan dito gaya ng isang tao. Puwede kang tumawag sa 988, ang "
           "Crisis Lifeline, anumang oras, araw man o gabi, at humingi ng interpreter sa Tagalog. Kung nasa panganib ka "
           "ngayon, tumawag ka sa 911.",
           ["Hahanapin ko po.", "Titingnan ko po ang buong kuwarto.", "Tingnan natin.", "Sige po.", "Ano po iyon?",
            "Tumigil na ako.", "Ayan na!", "Ayan na sila!", "Nakita ko na!", "Nakita ko na!", "Ah, ayan pala!",
            "Ah, ayan pala sila!"],
           ["susi", "salamin", "cellphone", "remote", "pitaka", "tasa", "baso", "relo", "bag", "libro", "bote", "payong"],
           "paalalahanan mo ako ng alas nuwebe ng umaga na diligan ang mga halaman",
           "Ipapaalala ko po sa inyo nang alas singko ng hapon na tawagan ang anak ninyong babae."),
    "vi": ("Vietnamese", "Tiếng Việt", "vie_Latn", "vie", "trên máy tính này", "Vâng, bây giờ tôi sẽ nói tiếng Việt.",
           "Tôi là Andy, một robot trí tuệ nhân tạo.",
           "Tôi là robot, nên tôi không thể giúp việc này như một người được. Quý vị có thể gọi 988, Đường dây Hỗ trợ "
           "Khủng hoảng, bất cứ lúc nào, ngày hay đêm, và xin một thông dịch viên tiếng Việt. Nếu "
           "quý vị đang gặp nguy hiểm ngay lúc này, xin hãy gọi 911.",
           ["Để tôi tìm.", "Để tôi nhìn quanh phòng.", "Để tôi xem.", "Vâng.", "Dạ?", "Tôi dừng rồi.", "Kia rồi!",
            "Kia rồi!", "Tìm thấy rồi!", "Tìm thấy rồi!", "À, kia rồi!", "À, kia rồi!"],
           ["chìa khóa", "kính", "điện thoại", "điều khiển", "ví", "cốc", "tách", "đồng hồ", "túi", "sách", "chai", "ô"],
           "nhắc tôi lúc chín giờ sáng tưới cây", "Tôi sẽ nhắc quý vị lúc 5 giờ chiều gọi cho con gái."),
    "ko": ("Korean", "한국어", "kor_Hang", "kor", "이 컴퓨터에서", "네, 이제 한국어로 말할게요.", "저는 앤디, 인공지능 로봇이에요.",
           "저는 로봇이라서 사람처럼 도와드릴 수가 없어요. 988 위기 상담 전화에 밤낮 언제든지 전화하셔서 한국어 "
           "통역을 요청하실 수 있어요. 지금 위험한 상황이시라면 911에 전화해 주세요.",
           ["찾아볼게요.", "방을 둘러볼게요.", "어디 볼게요.", "네.", "네?", "멈췄어요.", "저기 있어요!", "저기 있어요!",
            "찾았어요!", "찾았어요!", "아, 저기 있네요!", "아, 저기 있네요!"],
           ["열쇠", "안경", "휴대폰", "리모컨", "지갑", "머그잔", "컵", "손목시계", "가방", "책", "병", "우산"],
           "오전 아홉 시에 화분에 물 주라고 알려줘", "오후 5시에 따님께 전화하시라고 알려 드릴게요."),
    "ru": ("Russian", "Русский", "rus_Cyrl", "rus", "на этом компьютере", "Хорошо, теперь я буду говорить по-русски.",
           "Я Энди, робот с искусственным интеллектом.",
           "Я робот, поэтому не могу помочь с этим так, как помог бы человек. Вы можете в любое время дня и ночи "
           "позвонить по номеру 988, на линию помощи в кризисных ситуациях, и попросить русскоязычного переводчика. "
           "Если вы прямо сейчас в опасности, пожалуйста, позвоните 911.",
           ["Сейчас поищу.", "Сейчас осмотрю комнату.", "Сейчас посмотрю.", "Хорошо.", "Да?", "Остановился.",
            "Вон там!", "Вон они!", "Нашёл!", "Нашёл!", "А, вон там!", "А, вон они!"],
           ["ключи", "очки", "телефон", "пульт", "кошелёк", "кружка", "чашка", "часы", "сумка", "книга", "бутылка", "зонт"],
           "напомни мне в девять утра полить цветы", "Я напомню вам в 5 вечера позвонить дочери."),
    "ar": ("Arabic", "العربية", "arb_Arab", "arb", "على هذا الحاسوب", "حسنًا، سأتحدث العربية الآن.",
           "أنا آندي، روبوت يعمل بالذكاء الاصطناعي.",
           "أنا روبوت، لذلك لا أستطيع المساعدة في هذا كما يستطيع الإنسان. يمكنك الاتصال بالرقم 988، خط المساعدة في "
           "الأزمات، في أي وقت ليلًا أو نهارًا، وطلب مترجم للغة العربية. إذا كنت في خطر الآن، فاتصل "
           "بالرقم 911 من فضلك.",
           ["دعني أبحث.", "دعني أنظر في أرجاء الغرفة.", "دعني أرى.", "حسنًا.", "نعم؟", "توقفت.", "هناك!", "هناك!",
            "وجدت ما تبحث عنه!", "وجدت ما تبحث عنه!", "آه، هناك!", "آه، هناك!"],
           ["المفاتيح", "النظارة", "الهاتف", "جهاز التحكم", "المحفظة", "الكوب", "الفنجان", "الساعة", "الحقيبة", "الكتاب",
            "الزجاجة", "المظلة"],
           "ذكرني في التاسعة صباحًا أن أسقي النباتات", "سأذكّرك في الساعة 5 مساءً بالاتصال بابنتك."),
    "hi": ("Hindi", "हिन्दी", "hin_Deva", "hin", "इसी कंप्यूटर पर", "ठीक है, अब मैं हिन्दी में बात करूँगा।",
           "मैं एंडी हूँ, एक एआई रोबोट।",
           "मैं एक रोबोट हूँ, इसलिए इसमें मैं किसी इंसान की तरह मदद नहीं कर सकता। आप दिन हो या रात, किसी भी समय 988, "
           "क्राइसिस लाइफ़लाइन, पर कॉल कर सकते हैं और हिन्दी दुभाषिये के लिए कह सकते हैं। अगर आप अभी ख़तरे "
           "में हैं, तो कृपया 911 पर कॉल करें।",
           ["मैं ढूँढता हूँ।", "मैं कमरे में चारों ओर देखता हूँ।", "मैं देखता हूँ।", "ठीक है।", "जी?", "रुक गया।",
            "वहाँ है!", "वहाँ हैं!", "मिल गया!", "मिल गए!", "अरे, वहाँ है!", "अरे, वहाँ हैं!"],
           ["चाबियाँ", "चश्मा", "फ़ोन", "रिमोट", "बटुआ", "मग", "कप", "घड़ी", "बैग", "किताब", "बोतल", "छाता"],
           "मुझे सुबह नौ बजे पौधों को पानी देने की याद दिलाना", "मैं आपको शाम 5 बजे अपनी बेटी को फ़ोन करने की याद दिलाऊँगा।"),
    "pt": ("Portuguese", "Português", "por_Latn", "por", "neste computador", "Está bem, agora vou falar português.",
           "Eu sou o Andy, um robô com inteligência artificial.",
           "Sou um robô, então não posso ajudar com isso como uma pessoa pode. Você pode ligar para o 988, a linha de "
           "apoio em crises, a qualquer hora, de dia ou de noite, e pedir um intérprete de "
           "português. Se você estiver em perigo agora, por favor ligue para o 911.",
           ["Deixa eu procurar.", "Deixa eu olhar pela sala.", "Deixa eu ver.", "Está bem.", "Sim?", "Parei.",
            "Ali está!", "Ali estão!", "Achei!", "Achei!", "Ah, ali está!", "Ah, ali estão!"],
           ["chaves", "óculos", "celular", "controle remoto", "carteira", "caneca", "xícara", "relógio", "bolsa", "livro",
            "garrafa", "guarda-chuva"],
           "me lembra às nove da manhã de regar as plantas", "Vou lembrar você às 5 da tarde de ligar para sua filha."),
    "fr": ("French", "Français", "fra_Latn", "fra", "sur cet ordinateur", "D'accord, je vais parler français maintenant.",
           "Je suis Andy, un robot doté d'intelligence artificielle.",
           "Je suis un robot, je ne peux donc pas vous aider pour cela comme le ferait une personne. Vous pouvez appeler "
           "le 988, la ligne d'aide en cas de crise, à toute heure du jour ou de la nuit, et "
           "demander un interprète en français. Si vous êtes en danger en ce moment, appelez le 911, s'il vous plaît.",
           ["Je regarde.", "Je regarde dans la pièce.", "Voyons.", "D'accord.", "Oui ?", "Je m'arrête.", "C'est là !",
            "Les voilà !", "Trouvé !", "Trouvé !", "Ah, c'est là !", "Ah, les voilà !"],
           ["clés", "lunettes", "téléphone", "télécommande", "portefeuille", "mug", "tasse", "montre", "sac", "livre",
            "bouteille", "parapluie"],
           "rappelle-moi à neuf heures du matin d'arroser les plantes", "Je vous rappellerai à 17 h d'appeler votre fille."),
    "it": ("Italian", "Italiano", "ita_Latn", "ita", "su questo computer", "Va bene, adesso parlo italiano.",
           "Sono Andy, un robot con intelligenza artificiale.",
           "Sono un robot, quindi non posso aiutarla in questo come farebbe una persona. Può chiamare il 988, la linea di "
           "aiuto per le crisi, a qualsiasi ora, di giorno o di notte, e chiedere un "
           "interprete di italiano. Se è in pericolo in questo momento, per favore chiami il 911.",
           ["Cerco subito.", "Guardo nella stanza.", "Vediamo.", "Va bene.", "Sì?", "Mi fermo.", "È lì!", "Sono lì!",
            "Trovato!", "Trovato!", "Ah, è lì!", "Ah, sono lì!"],
           ["chiavi", "occhiali", "telefono", "telecomando", "portafoglio", "tazza", "tazza", "orologio", "borsa", "libro",
            "bottiglia", "ombrello"],
           "ricordami alle nove di mattina di annaffiare le piante", "Le ricorderò alle 17 di chiamare sua figlia."),
    "pl": ("Polish", "Polski", "pol_Latn", "pol", "na tym komputerze", "Dobrze, teraz będę mówić po polsku.",
           "Jestem Andy, robot ze sztuczną inteligencją.",
           "Jestem robotem, więc nie mogę w tym pomóc tak, jak pomógłby człowiek. O każdej porze dnia i nocy można "
           "zadzwonić pod numer 988, na linię wsparcia w kryzysie, i poprosić o tłumacza "
           "języka polskiego. W razie bezpośredniego zagrożenia proszę zadzwonić pod numer 911.",
           ["Już szukam.", "Rozejrzę się po pokoju.", "Zobaczmy.", "Dobrze.", "Tak?", "Zatrzymałem się.", "Tam jest!",
            "Tam są!", "Znalazłem!", "Znalazłem!", "A, tam jest!", "A, tam są!"],
           ["klucze", "okulary", "telefon", "pilot", "portfel", "kubek", "filiżanka", "zegarek", "torba", "książka",
            "butelka", "parasol"],
           "przypomnij mi o dziewiątej rano, żeby podlać kwiaty", "Przypomnę o 17:00, żeby zadzwonić do córki."),
    "de": ("German", "Deutsch", "deu_Latn", "deu", "auf diesem Computer", "Gut, ich spreche jetzt Deutsch.",
           "Ich bin Andy, ein Roboter mit künstlicher Intelligenz.",
           "Ich bin ein Roboter und kann Ihnen dabei nicht so helfen wie ein Mensch. Sie können jederzeit, Tag und Nacht, "
           "die 988 anrufen, die Krisen-Hotline, und um einen Dolmetscher für Deutsch bitten. "
           "Wenn Sie gerade in Gefahr sind, rufen Sie bitte die 911 an.",
           ["Ich schaue mal.", "Ich schaue mich im Zimmer um.", "Mal sehen.", "In Ordnung.", "Ja?", "Angehalten.",
            "Da drüben!", "Da sind sie!", "Gefunden!", "Gefunden!", "Ah, da drüben!", "Ah, da sind sie!"],
           ["Schlüssel", "Brille", "Handy", "Fernbedienung", "Geldbörse", "Becher", "Tasse", "Uhr", "Tasche", "Buch",
            "Flasche", "Regenschirm"],
           "erinnere mich um neun Uhr morgens daran, die Pflanzen zu gießen",
           "Ich erinnere Sie um 17 Uhr daran, Ihre Tochter anzurufen."),
    "uk": ("Ukrainian", "Українська", "ukr_Cyrl", "ukr", "на цьому комп'ютері", "Добре, тепер я говоритиму українською.",
           "Я Енді, робот зі штучним інтелектом.",
           "Я робот, тож не можу допомогти з цим так, як допомогла б людина. Ви можете будь-коли, вдень чи вночі, "
           "зателефонувати за номером 988, на лінію допомоги в кризових ситуаціях, і попросити україномовного "
           "перекладача. Якщо ви просто зараз у небезпеці, будь ласка, зателефонуйте 911.",
           ["Зараз пошукаю.", "Зараз огляну кімнату.", "Зараз подивлюся.", "Добре.", "Так?", "Зупинився.", "Он там!",
            "Он вони!", "Знайшов!", "Знайшов!", "А, он там!", "А, он вони!"],
           ["ключі", "окуляри", "телефон", "пульт", "гаманець", "горнятко", "чашка", "годинник", "сумка", "книжка",
            "пляшка", "парасолька"],
           "нагадай мені о дев'ятій ранку полити квіти", "Я нагадаю вам о 17:00 зателефонувати доньці."),
}

# Andy's answer to a health question, and to how someone feels (companion/safety.py HEALTH_REPLY and FEELINGS_REPLY),
# by hand: never a model's words, so never machine-translated either. 988 has help by text and in Spanish; in the
# others, by phone with an interpreter, as the crisis reply says.
EMERGENCY_LINES = {  # "If you need help, please call 911 right away. I'll find your phone." (safety.py EMERGENCY_REPLY)
    "zh": "如果您需要帮助，请马上拨打 911。我来帮您找手机。",
    "tl": "Kung kailangan mo ng tulong, tumawag ka agad sa 911. Hahanapin ko ang cellphone mo.",
    "vi": "Nếu quý vị cần giúp đỡ, xin hãy gọi 911 ngay. Tôi sẽ tìm điện thoại cho quý vị.",
    "ko": "도움이 필요하시면 지금 바로 911에 전화하세요. 제가 휴대폰을 찾아 드릴게요.",
    "ru": "Если вам нужна помощь, сразу звоните 911. Я найду ваш телефон.",
    "ar": "إذا كنت بحاجة إلى مساعدة، فاتصل بالرقم 911 فورًا. سأبحث عن هاتفك.",
    "hi": "अगर आपको मदद चाहिए, तो तुरंत 911 पर कॉल करें। मैं आपका फ़ोन ढूँढता हूँ।",
    "pt": "Se precisar de ajuda, ligue para o 911 agora mesmo. Vou procurar o seu celular.",
    "fr": "Si vous avez besoin d'aide, appelez le 911 tout de suite. Je vais chercher votre téléphone.",
    "it": "Se ha bisogno di aiuto, chiami subito il 911. Cerco il suo telefono.",
    "pl": "Jeśli potrzebna jest pomoc, proszę od razu zadzwonić pod numer 911. Poszukam telefonu.",
    "de": "Wenn Sie Hilfe brauchen, rufen Sie sofort die 911 an. Ich suche Ihr Telefon.",
    "uk": "Якщо вам потрібна допомога, одразу телефонуйте 911. Я знайду ваш телефон.",
}
HEALTH_LINES = {
    "zh": ("我是机器人，不能给您健康方面的建议，您的医生或药剂师可以。我可以提醒您给他们打电话。如果是紧急情况，请拨打 911。",
           "很抱歉您现在不好受。我是机器人，不能就您的感受给建议，但您的医生可以。您可以随时拨打 988，白天晚上都可以，并说您需要中文口译员。"),
    "tl": ("Robot ako, kaya hindi ako makapagbibigay ng payo tungkol sa kalusugan: ang doktor o parmasyutiko mo ang "
           "makakatulong. Puwede kitang paalalahanan na tawagan sila. Kung emergency ito, tumawag ka sa 911.",
           "Pasensya na at mahirap ito para sa iyo ngayon. Robot ako, kaya hindi ako makapagbibigay ng payo tungkol sa "
           "nararamdaman mo, pero ang doktor mo ay makakatulong. Puwede kang tumawag sa 988 anumang oras, araw man o "
           "gabi, at humingi ng interpreter sa Tagalog."),
    "vi": ("Tôi là robot nên không thể đưa ra lời khuyên về sức khỏe: bác sĩ hoặc dược sĩ của quý vị có thể giúp. Tôi có "
           "thể nhắc quý vị gọi cho họ. Nếu là trường hợp khẩn cấp, xin hãy gọi 911.",
           "Tôi rất tiếc vì lúc này quý vị đang thấy khó khăn. Tôi là robot nên không thể khuyên về cảm xúc của quý vị, "
           "nhưng bác sĩ của quý vị có thể. Quý vị có thể gọi 988 bất cứ lúc nào, ngày hay đêm, và xin một thông dịch "
           "viên tiếng Việt."),
    "ko": ("저는 로봇이라서 건강에 관한 조언은 드릴 수 없지만, 의사나 약사는 도와드릴 수 있어요. 그분들께 전화하시도록 알려 "
           "드릴 수 있어요. 응급 상황이라면 911에 전화해 주세요.",
           "지금 힘드시다니 안타까워요. 저는 로봇이라서 기분에 관한 조언은 드릴 수 없지만, 의사는 도와드릴 수 있어요. 988에 "
           "밤낮 언제든지 전화하셔서 한국어 통역을 요청하실 수 있어요."),
    "ru": ("Я робот, поэтому не могу давать советы о здоровье: это может сделать ваш врач или фармацевт. Я могу напомнить "
           "вам позвонить им. Если это экстренный случай, пожалуйста, позвоните 911.",
           "Мне жаль, что вам сейчас тяжело. Я робот, поэтому не могу советовать, как быть с тем, что вы чувствуете, но "
           "ваш врач может. Вы можете позвонить 988 в любое время, днём и ночью, и попросить переводчика с русского."),
    "ar": ("أنا روبوت، لذلك لا أستطيع تقديم نصائح صحية، لكن طبيبك أو الصيدلي يستطيع. يمكنني أن أذكّرك بالاتصال بهم. إذا "
           "كانت حالة طارئة، فاتصل بالرقم 911 من فضلك.",
           "يؤسفني أن الأمر صعب عليك الآن. أنا روبوت، لذلك لا أستطيع أن أنصحك بشأن ما تشعر به، لكن طبيبك يستطيع. يمكنك "
           "الاتصال بالرقم 988 في أي وقت ليلًا أو نهارًا، وطلب مترجم للغة العربية."),
    "hi": ("मैं एक रोबोट हूँ, इसलिए स्वास्थ्य के बारे में सलाह नहीं दे सकता, लेकिन आपके डॉक्टर या फ़ार्मासिस्ट दे सकते हैं। "
           "मैं आपको उन्हें फ़ोन करने की याद दिला सकता हूँ। अगर यह आपातकाल है, तो कृपया 911 पर कॉल करें।",
           "मुझे अफ़सोस है कि अभी आपके लिए मुश्किल समय है। मैं एक रोबोट हूँ, इसलिए आपकी भावनाओं के बारे में सलाह नहीं दे "
           "सकता, लेकिन आपके डॉक्टर दे सकते हैं। आप दिन हो या रात, किसी भी समय 988 पर कॉल करके हिन्दी दुभाषिये के लिए "
           "कह सकते हैं।"),
    "pt": ("Sou um robô, então não posso dar conselhos de saúde, mas o seu médico ou farmacêutico pode. Posso lembrar "
           "você de ligar para eles. Se for uma emergência, por favor ligue para o 911.",
           "Sinto muito que esteja difícil agora. Sou um robô, então não posso dar conselhos sobre o que você está "
           "sentindo, mas o seu médico pode. Você pode ligar para o 988 a qualquer hora, de dia ou de noite, e pedir um "
           "intérprete de português."),
    "fr": ("Je suis un robot, je ne peux donc pas donner de conseils de santé, mais votre médecin ou votre pharmacien, "
           "oui. Je peux vous rappeler de les appeler. Si c'est une urgence, appelez le 911, s'il vous plaît.",
           "Je suis désolé que ce soit difficile en ce moment. Je suis un robot, je ne peux donc pas vous conseiller sur "
           "ce que vous ressentez, mais votre médecin, oui. Vous pouvez appeler le 988 à toute heure du jour ou de la "
           "nuit et demander un interprète en français."),
    "it": ("Sono un robot, quindi non posso dare consigli sulla salute, ma il suo medico o il farmacista sì. Posso "
           "ricordarle di chiamarli. Se è un'emergenza, per favore chiami il 911.",
           "Mi dispiace che sia un momento difficile. Sono un robot, quindi non posso darle consigli su come si sente, "
           "ma il suo medico sì. Può chiamare il 988 a qualsiasi ora, di giorno o di notte, e chiedere un interprete di "
           "italiano."),
    "pl": ("Jestem robotem, więc nie mogę udzielać porad zdrowotnych, ale lekarz lub farmaceuta może. Mogę przypomnieć "
           "o telefonie do nich. W nagłym wypadku proszę zadzwonić pod numer 911.",
           "Przykro mi, że jest teraz ciężko. Jestem robotem, więc nie mogę doradzać w sprawie samopoczucia, ale lekarz "
           "może. O każdej porze dnia i nocy można zadzwonić pod numer 988 i poprosić o tłumacza języka polskiego."),
    "de": ("Ich bin ein Roboter und kann Ihnen keine Gesundheitsratschläge geben, aber Ihr Arzt oder Ihre Apotheke kann "
           "das. Ich kann Sie daran erinnern, dort anzurufen. Wenn es ein Notfall ist, rufen Sie bitte die 911 an.",
           "Es tut mir leid, dass es gerade schwer ist. Ich bin ein Roboter und kann Sie nicht dazu beraten, wie es Ihnen "
           "geht, aber Ihr Arzt kann das. Sie können jederzeit, Tag und Nacht, die 988 anrufen und um einen Dolmetscher "
           "für Deutsch bitten."),
    "uk": ("Я робот, тому не можу давати порад щодо здоров'я: це може зробити ваш лікар або фармацевт. Я можу нагадати "
           "вам зателефонувати їм. Якщо це невідкладний випадок, будь ласка, зателефонуйте 911.",
           "Мені шкода, що вам зараз важко. Я робот, тому не можу радити щодо того, що ви відчуваєте, але ваш лікар може. "
           "Ви можете будь-коли, вдень і вночі, зателефонувати 988 і попросити перекладача з української."),
}

for _code, _row in MORE.items():  # every language has every line and thing, in order
    assert len(_row) == 12 and len(_row[8]) == len(LINES) and len(_row[9]) == len(THINGS) and _code in HEALTH_LINES and _code in EMERGENCY_LINES, _code
