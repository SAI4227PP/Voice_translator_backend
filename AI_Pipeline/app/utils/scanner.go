package utils

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"voice_translator_go_server/app/config"
)

type Scanner struct {
	Settings config.Settings
}

func NewScanner(settings config.Settings) Scanner {
	return Scanner{Settings: settings}
}

var supportedTranslationLangs = map[string]string{
	"en": "English", "as": "Assamese", "bn": "Bengali", "brx": "Bodo", "doi": "Dogri",
	"gu": "Gujarati", "hi": "Hindi", "kn": "Kannada", "ks": "Kashmiri", "kok": "Konkani",
	"mai": "Maithili", "ml": "Malayalam", "mni": "Manipuri", "mr": "Marathi", "ne": "Nepali",
	"or": "Odia", "pa": "Punjabi", "sa": "Sanskrit", "sat": "Santali", "sd": "Sindhi",
	"ta": "Tamil", "te": "Telugu", "ur": "Urdu",
}

var supportedTTSLangs = supportedTranslationLangs

var sttNames = map[string]string{
	"en": "English", "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "kn": "Kannada",
	"ml": "Malayalam", "gu": "Gujarati", "mr": "Marathi", "bn": "Bengali",
}

func (s Scanner) GetAvailableSTTLanguages() map[string]map[string]string {
	result := map[string]map[string]string{}
	entries, err := os.ReadDir(s.Settings.VoskModelBasePath)
	if err == nil {
		for _, e := range entries {
			if !e.IsDir() {
				continue
			}
			name := e.Name()
			if !strings.HasPrefix(name, "vosk-") {
				continue
			}
			lang := strings.TrimPrefix(name, "vosk-")
			lang = strings.Split(lang, "-")[0]
			result[lang] = map[string]string{
				"name":  fallbackName(sttNames, lang),
				"model": name,
				"path":  filepath.ToSlash(filepath.Join(s.Settings.VoskModelBasePath, name)),
			}
		}
	}
	if len(result) > 0 {
		return result
	}
	return map[string]map[string]string{
		"en": {"name": "English", "model": "vosk-en", "path": "models/stt/vosk-en"},
		"hi": {"name": "Hindi", "model": "vosk-hi", "path": "models/stt/vosk-hi"},
		"te": {"name": "Telugu", "model": "vosk-te", "path": "models/stt/vosk-te"},
		"gu": {"name": "Gujarati", "model": "vosk-gu", "path": "models/stt/vosk-gu"},
		"bn": {"name": "Bengali", "model": "vosk-bn", "path": "models/stt/vosk-bn"},
	}
}

func (s Scanner) GetAvailableTranslationLanguages() map[string]map[string]string {
	result := map[string]map[string]string{}
	for code, name := range supportedTranslationLangs {
		result[code] = map[string]string{"name": name}
	}
	return result
}

func (s Scanner) GetAvailableTTSLanguages() map[string]map[string]any {
	result := map[string]map[string]any{}
	for code, name := range supportedTTSLangs {
		result[code] = map[string]any{
			"name":   name,
			"voices": []string{"anushka"},
			"model":  s.Settings.SvaraModelID,
		}
	}
	return result
}

func (s Scanner) GetTranslationPairs() []map[string]string {
	codes := make([]string, 0, len(supportedTranslationLangs))
	for c := range supportedTranslationLangs {
		codes = append(codes, c)
	}
	sort.Strings(codes)
	pairs := make([]map[string]string, 0, len(codes)*(len(codes)-1))
	for _, src := range codes {
		for _, tgt := range codes {
			if src == tgt {
				continue
			}
			pairs = append(pairs, map[string]string{
				"from": src,
				"to":   tgt,
				"name": supportedTranslationLangs[src] + " -> " + supportedTranslationLangs[tgt],
			})
		}
	}
	return pairs
}

func fallbackName(names map[string]string, code string) string {
	if v, ok := names[code]; ok {
		return v
	}
	return strings.ToUpper(code)
}
