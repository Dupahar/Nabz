# Benchmark results

6 scripted field-sales conversations (4 Hinglish, 2 Indian English), each rendered twice: with Gnani Timbre v3.0 voices and with ElevenLabs multilingual v2 voices. Phone ~1.7 m away in a simulated 7×5×3 m shop (RT60 0.5 s); street traffic, cafeteria (DEMAND) or 6-voice babble noise. WER = phonetic WER (`normalize.phonetic`, script-agnostic); spelling WER uses `normalize.normalize`. Brackets: 95% bootstrap CI over recordings. Pooled rows only include systems/conditions that ran on both sources.

## Pooled: both speech sources (12 recordings per condition)

### Word error rate (phonetic; lower is better)

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 2.0% [1%–3%] | 3.9% [3%–5%] | 12.7% [7%–19%] | 22.9% [14%–32%] | 44.8% [33%–58%] |
| Prisma v3.0 + denoise | – | – | 21.4% [12%–32%] | – | 56.2% [42%–72%] |
| Prisma v3.0 + keyterms | 2.0% [1%–3%] | – | 12.4% [7%–19%] | – | 45.1% [33%–59%] |
| Whisper medium | 10.3% [6%–15%] | – | 26.5% [14%–40%] | – | 49.4% [33%–68%] |
| Whisper small | 24.8% [14%–36%] | 32.6% [20%–46%] | 41.7% [24%–61%] | 53.5% [34%–77%] | 62.0% [45%–79%] |

### Keyterm recall: brands, competitors, amounts, days captured (higher is better)

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 94% [89%–98%] | 93% [89%–96%] | 89% [83%–94%] | 82% [72%–90%] | 59% [44%–73%] |
| Prisma v3.0 + denoise | – | – | 77% [65%–88%] | – | 45% [27%–64%] |
| Prisma v3.0 + keyterms | 93% [88%–98%] | – | 89% [84%–94%] | – | 60% [44%–74%] |
| Whisper medium | 71% [56%–85%] | – | 60% [40%–78%] | – | 42% [26%–57%] |
| Whisper small | 53% [37%–70%] | 46% [28%–64%] | 43% [22%–64%] | 34% [17%–52%] | 24% [10%–39%] |

## Gnani Timbre voices (6 recordings per condition)

### Word error rate (phonetic; lower is better)

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 1.8% [1%–3%] | 4.3% [2%–6%] | 11.3% [4%–20%] | 21.8% [10%–37%] | 40.7% [24%–63%] |
| Prisma v3.0 + denoise | 2.2% [1%–3%] | 6.8% [4%–10%] | 17.7% [7%–30%] | 34.3% [14%–57%] | 54.9% [33%–77%] |
| Prisma v3.0 + denoise + keyterms | 2.2% [1%–3%] | – | 17.5% [7%–30%] | – | 54.1% [32%–79%] |
| Prisma v3.0 + keyterms | 1.8% [1%–3%] | – | 11.3% [4%–20%] | – | 40.9% [24%–65%] |
| Whisper medium | 8.4% [4%–14%] | – | 22.6% [7%–39%] | – | 48.4% [22%–78%] |
| Whisper small | 27.3% [10%–46%] | 31.5% [14%–50%] | 35.0% [13%–58%] | 49.4% [21%–79%] | 57.6% [33%–82%] |

### Keyterm recall: brands, competitors, amounts, days captured (higher is better)

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 95% [88%–100%] | 93% [89%–97%] | 90% [80%–97%] | 82% [66%–94%] | 62% [38%–84%] |
| Prisma v3.0 + denoise | 92% [85%–97%] | 93% [86%–98%] | 77% [59%–92%] | 70% [45%–92%] | 44% [20%–71%] |
| Prisma v3.0 + denoise + keyterms | 92% [85%–97%] | – | 77% [55%–92%] | – | 48% [23%–72%] |
| Prisma v3.0 + keyterms | 95% [87%–100%] | – | 90% [80%–97%] | – | 64% [38%–84%] |
| Whisper medium | 77% [55%–97%] | – | 62% [33%–91%] | – | 43% [17%–65%] |
| Whisper small | 52% [27%–77%] | 48% [23%–73%] | 51% [21%–80%] | 36% [11%–62%] | 28% [6%–54%] |

## ElevenLabs voices (6 recordings per condition; independent TTS vendor)

### Word error rate (phonetic; lower is better)

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 2.1% [1%–3%] | 3.4% [2%–5%] | 14.1% [7%–23%] | 23.9% [11%–38%] | 48.9% [32%–66%] |
| Prisma v3.0 + denoise | – | – | 25.1% [10%–41%] | – | 57.6% [38%–77%] |
| Prisma v3.0 + keyterms | 2.1% [1%–3%] | – | 13.5% [6%–22%] | – | 49.4% [34%–66%] |
| Whisper medium | 12.2% [5%–19%] | – | 30.5% [14%–49%] | – | 50.5% [29%–77%] |
| Whisper small | 22.2% [10%–35%] | 33.6% [16%–53%] | 48.4% [22%–75%] | 57.6% [29%–87%] | 66.4% [44%–89%] |

### Keyterm recall: brands, competitors, amounts, days captured (higher is better)

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 93% [85%–99%] | 92% [85%–97%] | 89% [83%–94%] | 82% [69%–92%] | 56% [35%–74%] |
| Prisma v3.0 + denoise | – | – | 77% [60%–91%] | – | 46% [20%–74%] |
| Prisma v3.0 + keyterms | 92% [85%–97%] | – | 89% [83%–94%] | – | 56% [35%–74%] |
| Whisper medium | 66% [45%–84%] | – | 57% [33%–77%] | – | 41% [19%–62%] |
| Whisper small | 54% [31%–75%] | 44% [19%–68%] | 36% [9%–64%] | 33% [10%–57%] | 20% [3%–39%] |

## WER by language

### Hinglish (4 conversations), timbre

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 1.2% | 4.0% | 14.4% | 25.7% | 47.8% |
| Prisma v3.0 + denoise | 2.2% | 6.3% | 19.8% | 40.3% | 51.2% |
| Prisma v3.0 + denoise + keyterms | 2.2% | – | 19.8% | – | 51.2% |
| Prisma v3.0 + keyterms | 1.2% | – | 14.4% | – | 47.8% |
| Whisper medium | 11.9% | – | 34.0% | – | 68.2% |
| Whisper small | 41.3% | 47.4% | 52.6% | 72.1% | 78.3% |

### Indian English (2 conversations), timbre

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 3.0% | 4.9% | 5.6% | 14.6% | 27.7% |
| Prisma v3.0 + denoise | 2.2% | 7.9% | 13.9% | 23.2% | 61.8% |
| Prisma v3.0 + denoise + keyterms | 2.2% | – | 13.1% | – | 59.6% |
| Prisma v3.0 + keyterms | 3.0% | – | 5.6% | – | 28.1% |
| Whisper medium | 1.9% | – | 1.5% | – | 11.6% |
| Whisper small | 1.5% | 2.2% | 2.2% | 7.5% | 19.1% |

### Hinglish (4 conversations), elevenlabs

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 2.0% | 3.0% | 16.8% | 24.9% | 49.6% |
| Prisma v3.0 + denoise | – | – | 30.0% | – | 53.0% |
| Prisma v3.0 + keyterms | 2.0% | – | 16.6% | – | 48.8% |
| Whisper medium | 18.0% | – | 45.3% | – | 66.4% |
| Whisper small | 33.6% | 49.4% | 71.7% | 83.6% | 85.2% |

### Indian English (2 conversations), elevenlabs

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 2.2% | 4.1% | 9.0% | 22.1% | 47.6% |
| Prisma v3.0 + denoise | – | – | 16.1% | – | 65.9% |
| Prisma v3.0 + keyterms | 2.2% | – | 7.9% | – | 50.6% |
| Whisper medium | 1.5% | – | 3.0% | – | 21.0% |
| Whisper small | 1.1% | 4.5% | 5.2% | 9.4% | 31.5% |

## Spelling WER (stricter: a loanword written in Devanagari vs Latin counts as an error)

### timbre

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 5.0% | 6.6% | 13.0% | 22.9% | 42.2% |
| Prisma v3.0 + denoise | 4.6% | 8.7% | 19.3% | 35.9% | 57.2% |
| Prisma v3.0 + denoise + keyterms | 4.5% | – | 18.9% | – | 55.7% |
| Prisma v3.0 + keyterms | 4.7% | – | 13.0% | – | 42.4% |
| Whisper medium | 17.9% | – | 30.6% | – | 53.2% |
| Whisper small | 38.2% | 40.3% | 42.6% | 54.4% | 61.1% |

### elevenlabs

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 4.7% | 5.8% | 15.2% | 25.1% | 50.2% |
| Prisma v3.0 + denoise | – | – | 26.0% | – | 58.6% |
| Prisma v3.0 + keyterms | 5.0% | – | 14.7% | – | 50.9% |
| Whisper medium | 23.5% | – | 36.7% | – | 55.5% |
| Whisper small | 34.6% | 42.2% | 54.0% | 60.4% | 69.0% |

## Prisma speaker attribution (share of speech assigned to the right person)

### timbre

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 100% | 100% | 99% | 94% | 94% |
| Prisma v3.0 + denoise | 94% | 100% | 98% | 97% | 90% |
| Prisma v3.0 + denoise + keyterms | 94% | – | 98% | – | 90% |
| Prisma v3.0 + keyterms | 100% | – | 99% | – | 94% |

### elevenlabs

| System | Clean (close mic) | 20 dB | 10 dB | 5 dB | 0 dB |
|---|---|---|---|---|---|
| Prisma v3.0 | 100% | 100% | 99% | 98% | 87% |
| Prisma v3.0 + denoise | – | – | 96% | – | 88% |
| Prisma v3.0 + keyterms | 100% | – | 99% | – | 87% |

## Sanity check: original FieldNotes demo recordings (English, Windows TTS, clean, 2 files)

| System | WER |
|---|---|
| Prisma v3.0 | 2.6% |
| Whisper medium | 1.0% |
| Whisper small | 1.4% |

## Missed keyterms at 0 dB

- **Prisma v3.0**: industrial_pumps_en-el: Apex Hydra; Kirloskar (competitor); Mr. Nair | industrial_pumps_en: Kirloskar (competitor); Rs 1.8 lakh competitor quote; 15th | kirana_distributor-el: Parle-G; Maggi | kirana_distributor: Parle-G | loan_field_agent-el: Shakti Finance; Bajaj Finance (competitor) | loan_field_agent: Bajaj Finance (competitor) | logistics_d2c_en-el: ShipFast; Delhivery (competitor); WhatsApp; 1 December; Friday | logistics_d2c_en: Delhivery (competitor); Shiprocket (competitor); 22% RTO | pharma_detailing-el: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Rs 120 per strip; 20 strips of samples; Thursday | realestate_site_visit-el: 2 BHK; 1200 sq ft; March possession; Rs 70 lakh price; Godrej (competitor); HDFC; SBI; Rs 2 lakh booking | realestate_site_visit: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; HDFC; SBI
- **Prisma v3.0 + denoise**: industrial_pumps_en-el: Apex Hydra; Kirloskar (competitor); Rs 1.8 lakh competitor quote | industrial_pumps_en: Apex Hydra; Kirloskar (competitor); Rs 1.8 lakh competitor quote; Rs 30,000 difference; 15th | kirana_distributor-el: Sunrise Distributors; Parle-G; Maggi | kirana_distributor: Parle-G; Maggi | loan_field_agent: Bajaj Finance (competitor) | logistics_d2c_en-el: ShipFast; Delhivery (competitor); 22% RTO; WhatsApp; Rs 45 per shipment; 500 grams; Rs 40 offer; 1 December; Friday | logistics_d2c_en: ShipFast; Delhivery (competitor); Shiprocket (competitor); 22% RTO; WhatsApp; Rs 45 per shipment; Rs 40 offer; 1 December; Friday | pharma_detailing-el: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples; Thursday | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples | realestate_site_visit-el: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; Godrej (competitor); HDFC; SBI; Rs 2 lakh booking | realestate_site_visit: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; HDFC; SBI; Rs 2 lakh booking; Sunday
- **Prisma v3.0 + denoise + keyterms**: industrial_pumps_en: Apex Hydra; Kirloskar (competitor); Rs 1.8 lakh competitor quote; Rs 30,000 difference | kirana_distributor: Parle-G; Maggi | loan_field_agent: Bajaj Finance (competitor) | logistics_d2c_en: ShipFast; Delhivery (competitor); Shiprocket (competitor); 22% RTO; WhatsApp; Rs 45 per shipment; Rs 40 offer; 1 December; Friday | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples | realestate_site_visit: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; HDFC; SBI; Rs 2 lakh booking
- **Prisma v3.0 + keyterms**: industrial_pumps_en-el: Apex Hydra; Kirloskar (competitor); Mr. Nair | industrial_pumps_en: Kirloskar (competitor); Rs 1.8 lakh competitor quote | kirana_distributor-el: Parle-G; Maggi | kirana_distributor: Parle-G | loan_field_agent-el: Shakti Finance; Bajaj Finance (competitor) | loan_field_agent: Bajaj Finance (competitor) | logistics_d2c_en-el: ShipFast; Delhivery (competitor); WhatsApp; 1 December; Friday | logistics_d2c_en: Delhivery (competitor); Shiprocket (competitor); 22% RTO | pharma_detailing-el: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Rs 120 per strip; 20 strips of samples; Thursday | realestate_site_visit-el: 2 BHK; 1200 sq ft; March possession; Rs 70 lakh price; Godrej (competitor); HDFC; SBI; Rs 2 lakh booking | realestate_site_visit: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; HDFC; SBI
- **Whisper medium**: industrial_pumps_en-el: Kirloskar (competitor) | industrial_pumps_en: Kirloskar (competitor); Mr. Nair | kirana_distributor-el: Sunrise Distributors; Parle-G; Maggi; Tata Salt; Britannia (competitor); 30-day credit | kirana_distributor: Sunrise Distributors; Parle-G; Maggi; Tata Salt; Monday | loan_field_agent-el: Shakti Finance; Rs 3 lakh loan; 14% interest; 36-month tenure; PAN | loan_field_agent: 14% interest; 36-month tenure; Bajaj Finance (competitor); EMI Rs 10,200; PAN; GST | logistics_d2c_en-el: ShipFast; Delhivery (competitor); Shiprocket (competitor); WhatsApp; Friday | logistics_d2c_en: Delhivery (competitor); Shiprocket (competitor); 22% RTO | pharma_detailing-el: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples; Thursday | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples; Thursday | realestate_site_visit-el: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; Godrej (competitor); Rs 65 lakh competitor price; HDFC; SBI; Rs 2 lakh booking | realestate_site_visit: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; Godrej (competitor); HDFC; SBI; Rs 2 lakh booking; Sunday
- **Whisper small**: industrial_pumps_en-el: Apex Hydra; Kirloskar (competitor); Rs 2.1 lakh price; Mr. Nair | industrial_pumps_en: Kirloskar (competitor); Mr. Nair | kirana_distributor-el: Sunrise Distributors; Parle-G; Maggi; Tata Salt; Britannia (competitor); 15% margin; 30-day credit; Rs 48,000 total; Monday | kirana_distributor: Sunrise Distributors; Parle-G; Tata Salt; Britannia (competitor); 15% margin; 12% margin; 30-day credit; Rs 500 discount; Rs 48,000 total; Monday | loan_field_agent-el: Shakti Finance; Rs 3 lakh loan; 14% interest; 36-month tenure; Bajaj Finance (competitor); EMI Rs 10,200; Aadhaar; PAN; GST; Friday | loan_field_agent: Rs 3 lakh loan; 14% interest; 36-month tenure; Bajaj Finance (competitor); EMI Rs 10,200; Aadhaar; PAN; GST | logistics_d2c_en-el: ShipFast; Delhivery (competitor); Shiprocket (competitor); WhatsApp; 1 December; Friday | logistics_d2c_en: Delhivery (competitor); Shiprocket (competitor); 22% RTO; 1 December | pharma_detailing-el: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples; Thursday | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples; Thursday | realestate_site_visit-el: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; Godrej (competitor); Rs 65 lakh competitor price; HDFC; SBI; Rs 2 lakh booking; Sunday | realestate_site_visit: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; Godrej (competitor); Rs 65 lakh competitor price; HDFC; SBI; Rs 2 lakh booking; Sunday

## Missed keyterms on clean audio

- **Prisma v3.0**: industrial_pumps_en-el: Kirloskar (competitor) | logistics_d2c_en-el: Delhivery (competitor) | logistics_d2c_en: Delhivery (competitor) | pharma_detailing-el: Zenova Pharma; Metformin | pharma_detailing: Zenova Pharma; Glucosafe
- **Prisma v3.0 + denoise**: kirana_distributor: Parle-G | loan_field_agent: 36-month tenure | logistics_d2c_en: Delhivery (competitor) | pharma_detailing: Zenova Pharma; Glucosafe
- **Prisma v3.0 + denoise + keyterms**: kirana_distributor: Parle-G | loan_field_agent: 36-month tenure | logistics_d2c_en: Delhivery (competitor) | pharma_detailing: Zenova Pharma; Glucosafe
- **Prisma v3.0 + keyterms**: industrial_pumps_en-el: Kirloskar (competitor) | logistics_d2c_en-el: Delhivery (competitor) | logistics_d2c_en: Delhivery (competitor) | pharma_detailing-el: Zenova Pharma; Metformin | pharma_detailing: Zenova Pharma; Glucosafe | realestate_site_visit-el: RERA
- **Whisper medium**: industrial_pumps_en-el: Kirloskar (competitor) | kirana_distributor-el: Sunrise Distributors; Monday | kirana_distributor: Parle-G | loan_field_agent-el: Rs 3 lakh loan; EMI Rs 10,200; PAN; GST | logistics_d2c_en-el: Delhivery (competitor) | logistics_d2c_en: Delhivery (competitor) | pharma_detailing-el: Zenova Pharma; Glucosafe; Metformin; 20 strips of samples | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Type 2 diabetes; Rs 120 per strip; 20 strips of samples | realestate_site_visit-el: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; RERA; Rs 70 lakh price; Godrej (competitor); Rs 65 lakh competitor price; Rs 2 lakh booking | realestate_site_visit: Green Valley Residency; 1200 sq ft; March possession; Rs 70 lakh price; Rs 65 lakh competitor price; Rs 2 lakh booking
- **Whisper small**: industrial_pumps_en-el: Kirloskar (competitor); Rs 1.8 lakh competitor quote | kirana_distributor-el: Sunrise Distributors; Britannia (competitor); 15% margin; Rs 500 discount; Rs 48,000 total | kirana_distributor: Sunrise Distributors; Parle-G; Tata Salt; Britannia (competitor); 12% margin; Rs 500 discount | loan_field_agent-el: Rs 3 lakh loan; 14% interest; Aadhaar; PAN | loan_field_agent: Rs 3 lakh loan; 14% interest; 36-month tenure; Bajaj Finance (competitor); Aadhaar; PAN; GST | logistics_d2c_en-el: Delhivery (competitor) | logistics_d2c_en: Delhivery (competitor) | pharma_detailing-el: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Rs 120 per strip; 20 strips of samples | pharma_detailing: Zenova Pharma; Glucosafe; Metformin; Glycomet (competitor); Type 2 diabetes; Rs 120 per strip; 20 strips of samples; Thursday | realestate_site_visit-el: Green Valley Residency; 1200 sq ft; March possession; RERA; Rs 70 lakh price; Godrej (competitor); Rs 65 lakh competitor price; HDFC; SBI; Rs 2 lakh booking | realestate_site_visit: Green Valley Residency; 2 BHK; 1200 sq ft; March possession; Rs 70 lakh price; Rs 65 lakh competitor price; Rs 2 lakh booking
