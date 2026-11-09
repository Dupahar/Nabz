# Record this: a 90-second kirana visit (real voices, real noise)

**Who:** you as **Arjun**, a Northwind distributor rep, and a friend as **Sharma ji**, the kirana owner.
**Where:** somewhere really noisy. A shop, a street with traffic, a canteen. The noise is the point.
**How:** one phone on the counter or in your shirt pocket, using the normal voice recorder or a
Telegram voice note. Don't hold it up to anyone's mouth.
**Language:** speak naturally. Change words freely, mix in English, overlap a little. Don't read
like a script.

The phone number below is **made up**. Never use a real one.

---

**Arjun:** Namaste Sharma ji! Ek second, main ye baat record kar loon? Company training ke liye hai, bas.
**Sharma ji:** Haan haan, kar lo, koi baat nahi.

**Arjun:** Toh is hafte kaisa chal raha hai? Kya fast nikal raha hai?
**Sharma ji:** Parle-G aur Maggi toh roz khatam ho jaata hai. Woh naya wala Sunfeast Mom's Magic pada hua hai, nahi bik raha.

**Arjun:** Achha. Aur stock kitna bacha hai Parle-G ka?
**Sharma ji:** Bas do-teen packet. Paanch carton bhej do. Aur Maggi ke teen carton.

**Arjun:** Done. Aur is mahine scheme chal rahi hai: das carton pe ek carton free.
**Sharma ji:** Das carton? Itna jagah nahi hai bhai. Aur Britannia wala aadmi pandrah din ka credit de raha hai.

**Arjun:** Samajh gaya. Main manager se baat karke credit ka dekhta hoon. Abhi paanch aur teen likh deta hoon.
**Sharma ji:** Theek hai. Mera naya number likh lo: nau aath chaar paanch, zero ek do, teen chaar paanch.

**Arjun:** Likh liya. Payment kab tak?
**Sharma ji:** Friday ko UPI kar dunga, pakka.

**Arjun:** Perfect. Friday ko delivery ke saath bill aa jaayega. Dhanyavaad Sharma ji!

---

**What this exercises:**
- **Consent on tape.** `consent.py scan` finds it.
- **Hinglish** with brand names: Prisma `codemix` and keyterms.
- **Real noise:** `with_denoise`.
- **A spoken phone number** that gets redacted.
- **The `fmcg-retail` lens:** an order taken, a scheme explained but not landed, a stock check, the
  competitor Britannia offering credit, a slow mover (Mom's Magic), and a payment date.
- **Coaching:** the rep didn't upsell the slow mover, didn't check the shelf, and didn't counter the
  credit offer.

Send the file to the Telegram group (or to me) with the caption: `Sharma Kirana, consent ✅`

**Optional second recording, for the team report:** a friend as the rep "Sneha" visiting a pharmacy
(`pharma-detailing` lens). For a compliance flag, have the rep say *"Doctor sahab ko Goa trip ka
offer bhi hai is quarter"*. That's an inducement under UCPMP 2024, and the analyst should flag it
and tag the manager.
