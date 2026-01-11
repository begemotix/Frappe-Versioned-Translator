# Versioned Translator

Frappe App for Versioned Translations using DeepL API

## Installation

```bash
bench get-app versioned_translator
bench --site [your-site] install-app versioned_translator
```

## Features

- DeepL API integration for translations
- Versioned translation storage
- Smart field mapping for DocTypes
- Async translation processing
- Shadow storage for translations

## DocTypes

1. **Translation Settings** (Single DocType) - API configuration and global settings
2. **Translation Map** - Maps DocTypes and fields for translation
3. **Translation Store** - Shadow storage for translated content

## Usage

1. Configure Translation Settings with your DeepL API key
2. Create Translation Maps for DocTypes you want to translate
3. Translations are automatically processed on document update
