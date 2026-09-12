#!/usr/bin/env python3
"""
Siril Auto Stretch & Denoise Script
Automatikus képfeldolgozás: nyújtás és zajszűrés kijelölt háttérterület alapján.

Funkciók:
- Automatikus nyújtás (stretch) a háttér kijelölése alapján
- Szín természetességének megőrzése, csúcsfények megőrzése
- Háttér 0.18 sötétségben tartása
- Zajminta-alapú maszkolás
- Adaptív zajszűrés és kontrasztkiigazítás
"""

import os
import sys
import subprocess
import importlib.util
from pathlib import Path
from typing import Tuple, Optional
import json

# Automatikus függőségkezelés
def check_and_install_dependencies():
    """Ellenőrzi és telepíti a szükséges Python csomagokat."""
    required_packages = {
        'numpy': 'numpy',
        'cv2': 'opencv-python',
        'PIL': 'Pillow',
        'scipy': 'scipy',
        'skimage': 'scikit-image',
    }
    
    missing_packages = []
    
    for module_name, package_name in required_packages.items():
        if importlib.util.find_spec(module_name) is None:
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"📦 Hiányzó csomagok: {', '.join(missing_packages)}")
        print("🔄 Telepítés folyamatban...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
        print("✅ Telepítés kész")
    else:
        print("✅ Minden függőség telepítve van")

# Függőségek telepítése az import előtt
check_and_install_dependencies()

import numpy as np
import cv2
from PIL import Image
from scipy import ndimage
from scipy.ndimage import gaussian_filter, median_filter
from skimage import exposure, restoration


class SirilAutoProcessor:
    """Siril képfeldolgozó osztály."""
    
    def __init__(self, image_path: str):
        """
        Inicializálás.
        
        Args:
            image_path: A feldolgozandó kép elérési útja
        """
        self.image_path = Path(image_path)
        if not self.image_path.exists():
            raise FileNotFoundError(f"A kép nem található: {image_path}")
        
        # Kép betöltése
        self.original_image = cv2.imread(str(self.image_path), cv2.IMREAD_UNCHANGED)
        if self.original_image is None:
            raise ValueError(f"A kép nem tölthető be: {image_path}")
        
        # BGR -> RGB konverzió
        if len(self.original_image.shape) == 3:
            self.original_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)
        
        # Float normalizálás (0-1 tartomány)
        if self.original_image.dtype == np.uint8:
            self.image = self.original_image.astype(np.float32) / 255.0
        else:
            self.image = self.original_image.astype(np.float32)
            if self.image.max() > 1.0:
                self.image = self.image / self.image.max()
        
        self.working_image = self.image.copy()
        self.background_mask = None
        self.background_sample = None
        
        print(f"✅ Kép betöltve: {self.image_path.name}")
        print(f"   Méret: {self.image.shape}")
        print(f"   Tartomány: {self.image.min():.4f} - {self.image.max():.4f}")
    
    def create_background_mask_interactive(self) -> np.ndarray:
        """
        Interaktív háttér kijelölés Siril-ből.
        A felhasználó manuálisan jelöli ki a hátteret Siril-ben.
        
        Returns:
            Bináris maszk a kijelölt háttérterületről
        """
        print("\n🎯 Háttér kijelölés:")
        print("   1. Nyisd meg a képet Siril-ben")
        print("   2. Jelöld ki a CSAK háttérből álló terület(ek)et")
        print("      (csillagok, csillagköd részek nélkül)")
        print("   3. A kijelölést mentsd: Siril > Select > Save Selection as FITS")
        print("   4. Add meg a mentett kijelölés fájl elérési útját")
        
        selection_path = input("\n📁 Kijelölés FITS fájl elérési útja: ").strip()
        
        if not selection_path:
            print("❌ Kijelölés szükséges!")
            return None
        
        selection_path = Path(selection_path)
        if not selection_path.exists():
            print(f"❌ Fájl nem található: {selection_path}")
            return None
        
        # FITS fájl betöltése (ha van astropy)
        try:
            from astropy.io import fits
            with fits.open(str(selection_path)) as hdul:
                mask_data = hdul[0].data
                if len(mask_data.shape) > 2:
                    mask_data = mask_data[0]
                self.background_mask = (mask_data > 0).astype(np.uint8)
        except ImportError:
            print("⚠️  astropy nincs telepítve, egyszerű módot használok")
            # Fallback: PPM vagy egyéb formátum
            try:
                mask_img = cv2.imread(str(selection_path), cv2.IMREAD_GRAYSCALE)
                self.background_mask = (mask_img > 127).astype(np.uint8)
            except:
                print("❌ Kijelölés nem tölthető be")
                return None
        
        print(f"✅ Kijelölés betöltve: {self.background_mask.sum()} pixel")
        return self.background_mask
    
    def extract_background_sample(self) -> np.ndarray:
        """Háttérminta kinyerése a kijelölt maszkból."""
        if self.background_mask is None:
            print("❌ Nincs háttérmaszk")
            return None
        
        if len(self.image.shape) == 3:
            self.background_sample = self.image[self.background_mask > 0]
        else:
            self.background_sample = self.image[self.background_mask > 0].reshape(-1, 1)
        
        print(f"✅ Háttérminta: {self.background_sample.shape[0]} pixel")
        print(f"   Átlag: {self.background_sample.mean():.4f}")
        print(f"   Szórás: {self.background_sample.std():.4f}")
        
        return self.background_sample
    
    def calculate_stretch_parameters(self) -> Tuple[float, float, float]:
        """
        Nyújtás paramétereinek kiszámítása háttérminta alapján.
        
        Returns:
            (black_point, midpoint, white_point) értékek 0-1 tartományban
        """
        if self.background_sample is None:
            print("❌ Nincs háttérminta")
            return (0, 0.5, 1)
        
        # Háttér statisztika
        bg_mean = self.background_sample.mean()
        bg_std = self.background_sample.std()
        
        # Fekete pont: háttér átlaga - 2*szórás (de minimum 0)
        black_point = max(0, bg_mean - 2 * bg_std)
        
        # Fehér pont: a kép maximuma, vagy ha túl alacsony, becsülés
        white_point = self.image.max()
        if white_point < 0.5:
            white_point = min(1.0, bg_mean + 6 * bg_std)
        
        # Középpont (gamma) 0.6-0.8 között
        midpoint = 0.7
        
        print(f"\n📊 Nyújtás paraméterek:")
        print(f"   Fekete pont: {black_point:.4f}")
        print(f"   Középpont (gamma): {midpoint:.4f}")
        print(f"   Fehér pont: {white_point:.4f}")
        
        return (black_point, midpoint, white_point)
    
    def apply_stretch(self, black_point: float, midpoint: float, white_point: float) -> np.ndarray:
        """
        MTF nyújtás alkalmazása (Curves3 stílus).
        
        Args:
            black_point: Fekete pont (0-1)
            midpoint: Gamma érték
            white_point: Fehér pont (0-1)
        
        Returns:
            Nyújtott kép
        """
        if white_point <= black_point:
            print("❌ Érvénytelen nyújtási paraméterek")
            return self.working_image.copy()
        
        stretched = self.working_image.copy()
        
        # Normalizálás [black_point, white_point] tartományre
        stretched = (stretched - black_point) / (white_point - black_point)
        stretched = np.clip(stretched, 0, 1)
        
        # Gamma korrekció
        if midpoint != 0.5:
            gamma = -np.log(midpoint) / np.log(0.5)
            stretched = np.power(stretched, gamma)
        
        self.working_image = stretched
        
        print(f"✅ Nyújtás alkalmazva")
        print(f"   Új tartomány: {stretched.min():.4f} - {stretched.max():.4f}")
        
        return stretched
    
    def verify_background_level(self, target_level: float = 0.18) -> bool:
        """
        Háttér szintjének ellenőrzése és korrekciója.
        
        Args:
            target_level: Cél háttér szint (0.18 vagy más)
        
        Returns:
            Sikeres-e az ellenőrzés
        """
        if self.background_mask is None:
            return False
        
        # Aktuális háttér szint
        bg_pixels = self.working_image[self.background_mask > 0]
        current_bg = bg_pixels.mean()
        
        print(f"\n🔍 Háttér szint ellenőrzés:")
        print(f"   Cél: {target_level:.4f}")
        print(f"   Aktuális: {current_bg:.4f}")
        
        # Ha szükséges, korrekció
        if abs(current_bg - target_level) > 0.02:
            print(f"   ⚠️  Korrekció szükséges ({abs(current_bg - target_level):.4f} eltérés)")
            
            # Szintek enyhébb kiigazítása
            correction_factor = target_level / max(current_bg, 0.01)
            correction_factor = np.clip(correction_factor, 0.9, 1.1)
            
            self.working_image = self.working_image * correction_factor
            self.working_image = np.clip(self.working_image, 0, 1)
            
            print(f"   ✅ Korrekció: {correction_factor:.3f}x")
            return True
        
        print(f"   ✅ Háttér szint megfelelő")
        return True
    
    def create_noise_mask(self, dilation: int = 3, blur: int = 15) -> np.ndarray:
        """
        Zajmintán alapuló maszk létrehozása.
        A háttérhez hasonló területeket azonosítja.
        
        Args:
            dilation: Dilate kernel mérete
            blur: Gaussian blur kernel mérete
        
        Returns:
            Zajmaszk (0-1 tartomány)
        """
        if self.background_mask is None or self.background_sample is None:
            print("❌ Nincs háttér információ")
            return np.ones_like(self.working_image[:, :, 0]) if len(self.working_image.shape) == 3 else np.ones_like(self.working_image)
        
        print(f"\n🎭 Zajmaszk létrehozása...")
        
        # Szürkeárnyalat konverzió
        if len(self.working_image.shape) == 3:
            gray = np.mean(self.working_image, axis=2)
        else:
            gray = self.working_image.copy()
        
        # Háttér statisztika
        bg_mean = self.background_sample.mean()
        bg_std = self.background_sample.std()
        
        # Szín-alapú hasonlóság (szomszédsági távolság)
        tolerance = 3 * bg_std
        similarity = np.abs(gray - bg_mean) < tolerance
        
        # Morfológiai műveletek
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilation, dilation))
        similarity = cv2.dilate(similarity.astype(np.uint8), kernel, iterations=1)
        
        # Gaussian blur a zónák kiegyenlítéséhez
        noise_mask = gaussian_filter(similarity.astype(np.float32), sigma=blur/2)
        noise_mask = np.clip(noise_mask, 0, 1)
        
        print(f"✅ Zajmaszk készült: {(noise_mask > 0.5).sum()} pixel (erős)")
        
        return noise_mask
    
    def apply_adaptive_denoising(self, noise_mask: np.ndarray, strength: float = 0.7) -> np.ndarray:
        """
        Adaptív zajszűrés alkalmazása a zajmaszk alapján.
        
        Args:
            noise_mask: Zajmaszk (0-1)
            strength: Szűrés erőssége (0-1)
        
        Returns:
            Szűrt kép
        """
        print(f"\n🧹 Adaptív zajszűrés alkalmazása (erőssége: {strength:.1%})...")
        
        denoised = self.working_image.copy()
        
        # Non-Local Means Denoising (ha RGB)
        if len(self.working_image.shape) == 3:
            # OpenCV NLM csak uint8-kal működik, ezért konvertálunk
            img_uint8 = (self.working_image * 255).astype(np.uint8)
            denoised_uint8 = cv2.fastNlMeansDenoisingColored(
                img_uint8,
                None,
                h=10,
                hForColorComponents=10,
                templateWindowSize=7,
                searchWindowSize=21
            )
            denoised = denoised_uint8.astype(np.float32) / 255.0
        else:
            # Medián szűrés monokróm képhez
            denoised = cv2.medianBlur(
                (self.working_image * 255).astype(np.uint8),
                ksize=5
            ).astype(np.float32) / 255.0
        
        # Maszk alkalmazása (csak a zajterületeken)
        noise_mask_expanded = noise_mask
        if len(self.working_image.shape) == 3:
            noise_mask_expanded = np.stack([noise_mask] * 3, axis=2)
        
        # Blendolés: eredeti + szűrt, a maszk alapján
        blended = self.working_image * (1 - strength * noise_mask_expanded) + \
                  denoised * (strength * noise_mask_expanded)
        
        self.working_image = np.clip(blended, 0, 1)
        
        print(f"✅ Zajszűrés kész")
        return self.working_image
    
    def enhance_contrast_selective(self, noise_mask: np.ndarray, strength: float = 0.15) -> np.ndarray:
        """
        Szelektív kontrasztnövelés a zajmaszk alapján.
        
        Args:
            noise_mask: Zajmaszk (0-1)
            strength: Erőssége (0-1)
        """
        print(f"\n🎨 Szelektív kontrasztkiigazítás (erőssége: {strength:.1%})...")
        
        if len(self.working_image.shape) == 3:
            # LAB színtérre váltás a természetesebb eredmény érdekében
            lab = cv2.cvtColor((self.working_image * 255).astype(np.uint8), cv2.COLOR_RGB2LAB)
            L = lab[:, :, 0].astype(np.float32) / 255.0
            
            # Kontrasztnövelés csak a zajterületeken
            L_enhanced = exposure.adjust_sigmoid(L, cutoff=0.5, gain=1 + strength * 2)
            
            # Maszk alkalmazása
            L_blended = L * (1 - strength * noise_mask) + L_enhanced * (strength * noise_mask)
            
            lab[:, :, 0] = (L_blended * 255).astype(np.uint8)
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).astype(np.float32) / 255.0
        else:
            enhanced = exposure.adjust_sigmoid(self.working_image, cutoff=0.5, gain=1 + strength * 2)
            enhanced = self.working_image * (1 - strength * noise_mask) + enhanced * (strength * noise_mask)
        
        self.working_image = np.clip(enhanced, 0, 1)
        
        print(f"✅ Kontrasztkiigazítás kész")
        return self.working_image
    
    def save_result(self, output_path: Optional[str] = None) -> Path:
        """
        Feldolgozott kép mentése.
        
        Args:
            output_path: Kimeneti fájl elérési útja (alapértelmezés: _processed)
        
        Returns:
            Mentett fájl elérési útja
        """
        if output_path is None:
            output_path = self.image_path.stem + "_processed.tif"
        
        output_path = Path(output_path)
        
        # RGB -> BGR konverzió mentés előtt
        save_image = (self.working_image * 255).astype(np.uint8)
        if len(save_image.shape) == 3:
            save_image = cv2.cvtColor(save_image, cv2.COLOR_RGB2BGR)
        
        cv2.imwrite(str(output_path), save_image)
        
        print(f"\n💾 Kép mentve: {output_path}")
        return output_path
    
    def process_full_pipeline(self) -> Path:
        """
        Teljes feldolgozási folyamat futtatása.
        
        Returns:
            Feldolgozott kép elérési útja
        """
        print("\n" + "="*60)
        print("🚀 SIRIL AUTO STRETCH & DENOISE - Feldolgozás indítása")
        print("="*60)
        
        # 1. Háttér kijelölés
        if self.create_background_mask_interactive() is None:
            print("❌ Feldolgozás szakított: háttér kijelölés szükséges")
            return None
        
        # 2. Háttérminta kinyerése
        self.extract_background_sample()
        
        # 3. Nyújtás paraméterek
        black_pt, midpt, white_pt = self.calculate_stretch_parameters()
        
        # 4. Nyújtás alkalmazása (lehet többlépcsős)
        self.apply_stretch(black_pt, midpt, white_pt)
        
        # 5. Háttér szint ellenőrzése és korrekciója
        self.verify_background_level(target_level=0.18)
        
        # 6. Zajmaszk létrehozása
        noise_mask = self.create_noise_mask(dilation=3, blur=15)
        
        # 7. Zajszűrés
        self.apply_adaptive_denoising(noise_mask, strength=0.7)
        
        # 8. Kontrasztkiigazítás
        self.enhance_contrast_selective(noise_mask, strength=0.15)
        
        # 9. Mentés
        result_path = self.save_result()
        
        print("\n" + "="*60)
        print("✅ FELDOLGOZÁS KÉSZ!")
        print("="*60)
        
        return result_path


def main():
    """Főprogram."""
    print("\n🔬 Siril Auto Stretch & Denoise")
    print("Csillagköd képfeldolgozó script\n")
    
    # Képfájl elérési útja
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = input("📁 Add meg a kép elérési útját: ").strip()
    
    if not image_path:
        print("❌ Hiányzó fájl elérési út")
        return 1
    
    try:
        processor = SirilAutoProcessor(image_path)
        result = processor.process_full_pipeline()
        
        if result:
            print(f"\n🎉 Feldolgozás sikeres: {result}")
            return 0
        else:
            print("\n❌ Feldolgozás mégsem teljesült")
            return 1
    
    except Exception as e:
        print(f"\n❌ Hiba: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
