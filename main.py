from fastapi import FastAPI, HTTPException
import requests
import re
from bs4 import BeautifulSoup

app = FastAPI(title="Netzverb API")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,de;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Track": "1",
    "Upgrade-Insecure-Requests": "1"
}

def _parse_verbformen(soup: BeautifulSoup, w: str) -> dict:
  # Variables del elemento
  type = None
  gender = None
  translate = None
  context = None
  example = None

  #? ========== Elementos del documento ==========
  article = soup.find("article")
  if not article: return {}
  
  sections = article.find_all("div", class_="rAufZu")
  if not sections: return {}

  first_section = sections[0]
  example_section = None
  
  for section in sections:
    child = section.find("ul", class_="rLst rLstGt", recursive=False)
    if child:
      example_section = child
      break
  
  header_context = first_section.find("p", class_="rInf")
  forms = first_section.find("p", class_="vStm rCntr")

  #? ==================== Obtener datos ====================
  
  # ========== Obtener palabra ==========
  word_input = article.find("input", {'name': 'word'})
  word = word_input['value'].lower() if word_input else None

  if word != w:
    word = f"{word} (coincidencia no exacta)"

  # ========== Obtener el tipo ==========
  type_input = article.find("input", {'name': 'word_type'})
  type = type_input['value'].lower() if type_input else None

  # ========== Obtener el género ==========
  if type == "noun":
    span_vGrnd = first_section.find("span", class_="vGrnd")
    if span_vGrnd and span_vGrnd.contents: 
      art = span_vGrnd.contents[0].replace(' ', '')
      word = f"{art} {word}".title()
    
      # Obtener el género
      if art == "der": gender = "m."
      elif art == "das": gender = "n."
      else: gender = "f."

  # ========== Buscar la traducción ==========
  span_es = first_section.find("span", attrs={'lang': 'es'})
  if span_es:
    text_translate = span_es.text
    translates = text_translate.replace('\n', '').strip().split(", ")[:3]
    translate = " - ".join(translates).title()
  
  # ========== Buscar el contexto específico ==========
  if type == "verb":
    context = forms.text.strip().replace("\n", "").replace("·", "|")
  elif type == "noun":
    header_context_elements = header_context.find_all("span")[2:]
    if header_context_elements:
      context = " | ".join([element.text for element in header_context_elements])
  elif type == "adjective":
    if not re.search("-", forms.text):
      context = forms.text.strip().replace("\n", "").replace("·", " | ")
    else:
      context = f"{re.sub(r'[-\n·]', '', forms.text).strip()} | No comparable"
  elif type == "article" or type == "pronoun":
    level = header_context.find(class_="bZrt")
    header_context_elements = header_context.find_all() if not level else header_context.find_all()[1:]
    context = " | ".join(element.text for element in header_context_elements).title()
  else:
    header_context_elements = header_context
  
  # ========== Buscar un ejemplo ========== 
  if example_section and example_section.find():
    example = re.sub(r"\s*\u00A0\s*\u00A0\s*", " - ", example_section.find().text)
    example = re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"\s+", " ", example)).strip()

  return {
    "word": word,
    "type": type.title(),
    "gender": gender,
    "translate": translate,
    "context": context,
    "example": example
  }

def _parse_woerter(soup: BeautifulSoup, w: str) -> dict:
  # Variables del elemento
  type = None
  gender = None
  translate = None
  context = None
  example = None

  #? ========== Elementos del documento ==========
  article = soup.find("article")
  if not article: return {}

  sections = article.find_all("div", class_="rAufZu")
  if not sections: return {}

  form = article.find("form")
  if not form: return {}

  first_section = sections[0]
  example_section = None

  for section in sections:
    child = section.find("ul", class_="rLst rLstGt", recursive=False)
    if child:
      example_section = child
      break
  
  header_context = first_section.find("span", class_="rInf")
  first_section_content = first_section.find("p", class_="r1Zeile rU6px rO0px")

  #? ==================== Obtener datos ====================
  
  # ========== Obtener palabra ==========
  word_input = form.find("input", {'name': 'word'})
  word = word_input['value'].lower() if word_input else None

  if word != w:
    word = f"{word} (coincidencia no exacta)"

  # ========== Obtener el tipo ==========
  type_input = form.find("input", {'name': 'word_type'})
  type = type_input['value'].lower() if type_input else None

  match type:
    case "praeposition":
      type = "preposition"
    case "konjunktion":
      type = "conjunction"


  # ========== Buscar la traducción ==========
  span_es = first_section_content.find("span", attrs={'lang': 'es'})
  if span_es:
    text_translate = span_es.text
    translates = text_translate.replace('\n', '').strip().split(", ")[:3]
    translate = " - ".join(translates).title()

  # ========== Buscar el contexto específico ==========
  if type == "adverb":
    context = None
  elif type == "preposition":
    level = header_context.find(class_="bZrt")
    header_context_elements = header_context.find_all()[1:] if not level else header_context.find_all()[2:]
    context = " | ".join(element.text for element in header_context_elements).title() or None
  elif type == "conjunction":
    header_context_elements = header_context.find_all()[2:]
    context = " | ".join(element.text for element in header_context_elements).title()
  elif type == "particle":
    context = None
  else:
    header_context_elements = header_context

  # ========== Buscar un ejemplo ========== 
  if example_section and example_section.find():
    example = re.sub(r"\s*\u00A0\s*\u00A0\s*", " - ", example_section.find().text)
    example = re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"\s+", " ", example)).strip()

  return {
    "word": word,
    "type": type.title(),
    "gender": gender,
    "translate": translate,
    "context": context,
    "example": example
  }

@app.get('/')
def inicio():
  return {
    "message": "API lista"
  }

@app.get('/api/word')
def search(w: str, c: str = ""):

  session = requests.Session()
  session.headers.update(headers)
  
  verify = True
  url = ""

  match c.lower():
    case "verb": 
      url = f"https://www.verbformen.es/conjugacion/{w}.htm"
    case "noun": 
      url = f"https://www.verbformen.es/declinacion/sustantivos/{w}.htm"
    case "adjective": 
      url = f"https://www.verbformen.es/declinacion/adjetivos/{w}.htm"          
    case "adverb":
      url = f"https://www.woerter.es/adverbios/{w}.htm"
      verify = False
    case "article": 
      url = f"https://www.verbformen.es/declinacion/articulos/{w}.htm"
    case "pronoun": 
      url = f"https://www.verbformen.es/declinacion/pronombres/{w}.htm"
    case "preposition":
      url = f"https://www.woerter.es/prepositions/{w}.htm"
      verify = False
    case "conjunction":
      url = f"https://www.woerter.es/conjunctions/{w}.htm"
      verify = False
    case "particle":
      url = f"https://www.woerter.es/particles/{w}.htm"
      verify = False
    case "": 
      url = f"https://www.verbformen.es/?w={w}"
    case _:
      raise HTTPException(status_code=404, detail="Tipo de palabra no válida")

  try:
    response = session.get(url, timeout=10, verify=verify)

    if response.status_code != 200:
      if response.status_code == 429:
        raise HTTPException(status_code=response.status_code, detail=f"Demasiadas solicitudes de la API. Intente más tarde.")
      raise HTTPException(status_code=response.status_code, detail=f"No se puede acceder a la URL o {w} ({c}) no encontrado")
    

    # Análisis del HTML
    soup = BeautifulSoup(response.content, 'html.parser')
    article = soup.find("article")
    if not article:
      raise HTTPException(status_code=404, detail="Estructura de página inválida")
    
    homographs = None
    if not c:
      homographs = article.find_all("a", class_="rKnpf rNoSelect rLinks")

    # Variables generales
    list_word = []
    list_match = []
    content = []

    #* ==================== Verificar si existe una lista de coincidencias ====================
    i_tag = article.find("i")
    has_no_results = i_tag and re.search(f"No se encontraron palabras con '{w}'", i_tag.text)
    search_results = article.find_all("div", class_="bTrf rClear")

    if has_no_results and not search_results:
      raise HTTPException(status_code=404, detail=f"No se encontraron palabras con '{w}'")

    #* ==================== Procesar lista de coincidencias con varios resultados ====================
    if search_results:
      for li in search_results:
        # ========== Lógica para obtener la palabra y el enlace ==========
        header = li.find("div", class_="rU6px rO0px")
        if not header: continue

        title = header.text
        formatted_title = re.sub(r"[\n<>]", "", title).replace(' ', ' / ').replace(',', ' - ').strip()

        link = str(header.find("a").get_attribute_list("href"))
        formatted_link = re.sub(r"[\'\[\]]", "", link)

        # Completar la URL si la ruta es relativa
        if not re.search('http', formatted_link):
            formatted_link = f"https://www.verbformen.es{formatted_link}"

        # ========== Lógica para obtener el tipo ==========
        level = li.find("span", class_="bZrt")

        # Evaluar si hay nivel para obtener el tipo
        item = level.find_next() if level else li.find("span")
        text_item = item.text if item else None

        # Agregar el género en caso de sustantivo
        if text_item == "sustantivo" and item.find_next():
          text_item = f"{text_item} {item.find_next().text}"
        
        # ========== Objeto a retornar y adición al array ==========
        new_element = {
          "type": text_item,
          "word": formatted_title,
          "path": formatted_link
        }
        
        # Registrar coincidencia exacta
        if formatted_title == w:
          list_match.append(new_element)

        list_word.append(new_element)

      #? ==================== Consultar la URL si existe una única coincidencia exacta ====================
      if len(list_match) == 1:
        url = list_match[0]["path"]

        if re.search('woerter', url):
          url = url.replace(".net", ".es")
          verify = False

        # ========== Nueva búsqueda ==========
        response = session.get(url, timeout=10, verify=verify)
        soup = BeautifulSoup(response.text, 'html.parser')
      else:
        # ========== Lista de palabras si no hay nueva búsqueda ==========
        content = list_word
    
    #? ==================== Procesar homógrafos ====================
    if homographs and not search_results:
      list_homograph = []

      for homograph in homographs:
        #* ==================== Lógica para verbformen ====================
        if re.search("verbformen", url):
          # ========== Lógica para obtener el tipo de palabra ==========
          homo_header = homograph.find("div", class_="rKln rInf")
          homo_type = homo_header.find().text if (homo_header and homo_header.find()) else (homo_header.text.replace('\n', '') if homo_header else None)
          if homo_type in ["femenino", "masculino", "neutro"]:
            homo_type = f"sustantivo {homo_type}"
          homo_title = homograph.find("b").text if homograph.find("b") else None
        #* ==================== Lógica para woerter ====================
        else:
          homo_header = homograph.find("div", class_="rKln rInf")
          homo_type = homo_header.text.replace("\n", "") if homo_header else None
          if homo_type in ["femenino", "masculino", "neutro"]:
            homo_type = f"sustantivo {homo_type}"
          homo_title = homograph.find("q").text if homograph.find("q") else None
        
        # ========== Lógica para obtener el link ==========
        homo_link = str(homograph.get_attribute_list("href"))
        formatted_homo_link = re.sub(r"[\'\[\]]", "", homo_link)

        base_domain = "https://www.verbformen.es" if re.search("verbformen", url) else "https://www.woerter.es"
        if not re.search("http", formatted_homo_link):
          formatted_homo_link = f"{base_domain}{formatted_homo_link}"

        # ========== Objeto a retornar y adición al array ==========
        new_element = {
          "type": homo_type,
          "word": homo_title,
          "path": formatted_homo_link
        }
        
        if homo_title == w:
          list_match.append(new_element)
        list_homograph.append(new_element)

      if not len(list_match) > 0:
        content = list_homograph
    
    #? ==================== Extraer los datos de la palabra ====================
    if len(list_match) <= 1 and not content:
      if re.search("woerter", url):
        content = _parse_woerter(soup, w.lower())
      else:
        content = _parse_verbformen(soup, w.lower())

    #? ==================== Estructurar la respuesta ====================
    # ========== Determinar el estado semántico de la respuesta ==========
    if content and isinstance(content, dict):
      status_code = "success"
      payload = content
    elif content and isinstance(content, list):
      status_code = "ambiguous"
      payload = content
    elif len(list_match) > 1:
      status_code = "ambiguous"
      payload = list_match
    else:
      status_code = "success"
      payload = content

    return {
      "status": status_code,
      "status_code": response.status_code,
      "meta": {
        "requested_word": w,
        "requested_type": c if c else None,
        "source_url": url
      },
      "data": payload
    }
  except HTTPException as http_ex:
    raise http_ex
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"{str(e)}")
