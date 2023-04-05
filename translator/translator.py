from googletrans import Translator

supported_lang = ['🇮🇷','🇷🇺','🇩🇪','🇺🇸']

lang_format = {
    '🇮🇷' : 'fa' ,
    '🇷🇺' : 'ru',
    '🇩🇪' : 'de',
    '🇺🇸' : 'en'
}

def eng_translator(text,choosed_lang):

    translator = Translator()
    
    lang_detector = translator.detect(text).lang
    
    if choosed_lang in lang_format:

        translated = translator.translate(text , src=lang_detector,dest=lang_format[choosed_lang]).text
        return translated
    
    else:
        
        return text
    