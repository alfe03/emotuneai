import re

text = """{
  "emotion": "Hüzünlü ve keyifsiz",
  "emoji": "😔",
  "confidence": 95,
  "mood_category": "melancholic",
  "explanation": "Bugün kendini pek iyi hissetmediğini belirterek enerjinin ve keyfinin düşük olduğunu, biraz buruk ve hüzünlü hissettiğini paylaştın.",
  "requested_artist": null
}"""

match = re.search(r'\{(?:[^{}]|\{[^{}]*\})*\}', text)
print('MATCHED:', match is not None)
if match:
    print('RESULT:')
    print(match.group())
