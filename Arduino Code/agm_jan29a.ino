#include <Filters.h> 
#include "HX711.h"
#include <math.h> 

// --- PIN TANIMLAMALARI ---
const int DOUT_1 = 2; const int SCK_1 = 3; // Sağ Ayak
const int DOUT_2 = 4; const int SCK_2 = 5; // Sol Ayak
const int DOUT_3 = 7; const int SCK_3 = 8; // Ön Ayak

// --- GEOMETRİK AYARLAR (ÇOK ÖNEMLİ) ---
// d: ana daire merkezinden loadcell merkezine olan uzaklık (cm cinsinden ölçüp buraya yaz)
float d = 14.5; 

// Sensör Koordinatları (Çizimdeki 150 derece açısına göre hesaplanmıştır)
// Ön Ayak (L3) Koordinatları (Tam Y ekseni üstü)
float X3 = 0.0;
float Y3 = d;

// Sağ Ayak (L1) Koordinatları (Sin150 = 0.5, Cos150 = -0.866)
float X1 = d * 0.7071;     
float Y1 = d * -0.7071;  

// Sol Ayak (L2) Koordinatları (Simetrik)
float X2 = -d * 0.7071;      
float Y2 = d * -0.7071;   

// --- NESNE VE DEĞİŞKENLER ---
HX711 scale1; HX711 scale2; HX711 scale3;

// Filtreler
Filter::LPF<float> lpf1(0.05f); // Biraz daha hızlandırdım (CG tepkisi için)
Filter::LPF<float> lpf2(0.05f); 
Filter::LPF<float> lpf3(0.05f); 

// Kalibrasyon Değerlerin (En son belirlediklerimiz)
float cal_1 = 385.4;  // Sağ
float cal_2 = -400.8; // Sol
float cal_3 = 374.2;  // Ön

void setup() {
    Serial.begin(9600);
    Serial.println("Sistem Baslatiliyor...");
    Serial.println("Agirlik Merkezi (CG) Tespit Modu");

    scale1.begin(DOUT_1, SCK_1); scale1.set_scale(cal_1);
    scale2.begin(DOUT_2, SCK_2); scale2.set_scale(cal_2);
    scale3.begin(DOUT_3, SCK_3); scale3.set_scale(cal_3);

    Serial.println("Dara aliniyor...");
    delay(1000); 
    scale1.tare(); scale2.tare(); scale3.tare();

    Serial.println("--- SISTEM HAZIR ---");
}

void loop() {
    static float prev_t = millis() / 1000.f;
    float curr_t = millis() / 1000.f;
    float dt = curr_t - prev_t;
    prev_t = curr_t;

    // 1. Ağırlıkları Oku ve Filtrele
    float w1 = lpf1.get(scale1.get_units(1), dt); // Sağ
    float w2 = lpf2.get(scale2.get_units(1), dt); // Sol
    float w3 = lpf3.get(scale3.get_units(1), dt); // Ön

    // Deadzone (Çok küçük değerleri yoksay)
    if (w1 > -1.0 && w1 < 1.0) w1 = 0.0;
    if (w2 > -1.0 && w2 < 1.0) w2 = 0.0;
    if (w3 > -1.0 && w3 < 1.0) w3 = 0.0;

    // 2. Toplam Ağırlık
    float totalWeight = w1 + w2 + w3;

    // 3. Ağırlık Merkezi (CG) Hesabı
    float X_cg = 0.0;
    float Y_cg = 0.0;

    // Eğer tepside kayda değer bir ağırlık yoksa CG hesaplama (Sıfıra bölünme hatası olmasın)
    if (totalWeight > 10.0) { 
        float MomentX = (w1 * X1) + (w2 * X2) + (w3 * X3);
        float MomentY = (w1 * Y1) + (w2 * Y2) + (w3 * Y3);
        
        X_cg = MomentX / totalWeight;
        Y_cg = MomentY / totalWeight;
    }

    // 4. PYTHON ARAYÜZÜ İÇİN ÖZEL YAZDIRMA FORMATI
    // (Arayüz verileri bu anahtar kelimelere göre cımbızla çeker)
    Serial.print("Agirlik: "); Serial.print(totalWeight, 1);
    Serial.print("  X_CG: ");  Serial.print(X_cg, 2);
    Serial.print("  Y_CG: ");  Serial.print(Y_cg, 2);
    
    // Doğru Ayak Eşleşmeleri (UI etiketlerine göre):
    Serial.print("  LC1: "); Serial.print(w3, 1); // Python'daki LC1 (Front) -> Arduino w3 (Ön)
    Serial.print("  LC2: "); Serial.print(w2, 1); // Python'daki LC2 (Left)  -> Arduino w2 (Sol)
    Serial.print("  LC3: "); Serial.println(w1, 1); // Python'daki LC3 (Right)-> Arduino w1 (Sağ)
    
    delay(50); 
}