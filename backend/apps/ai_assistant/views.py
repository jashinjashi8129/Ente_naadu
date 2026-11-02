import os
import json
import urllib.request
import urllib.error
from django.conf import settings
from rest_framework import views, status, permissions
from rest_framework.response import Response

from apps.shops.models import Shop, ShopCategory
from apps.events.models import EventNotice
from apps.directory.models import DirectoryEntry, BloodDonor

class NattuSahayiChatView(views.APIView):
    """
    നാട്ടു സഹായി (Village AI Assistant) API endpoint.
    - Zero external library bloat (uses Python standard urllib).
    - Free Tier compatible with Google Gemini 1.5 Flash (or local intelligent fallback).
    - Injects real-time community context (open shops, active notices, emergency contacts).
    - Rate-limited to prevent abuse.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'ai_assistant'

    def _build_community_context(self):
        """
        Gathers live context from the database so the AI knows real village data.
        """
        open_shops = list(Shop.objects.filter(is_verified=True, is_open=True).values('name', 'contact_phone', 'ward_number', 'todays_offer')[:10])
        recent_notices = list(EventNotice.objects.all().order_by('-is_emergency', '-created_at').values('title', 'is_emergency', 'venue')[:5])
        emergency_services = list(DirectoryEntry.objects.filter(is_emergency_service=True).values('name', 'category', 'phone_number')[:8])

        context_str = "നിലവിലെ തത്സമയ ഗ്രാമ വിവരങ്ങൾ (Real-time Village Context):\n"

        if open_shops:
            context_str += "- ഇപ്പോൾ തുറന്ന കടകൾ:\n"
            for s in open_shops:
                offer = f", ഓഫർ: {s['todays_offer']}" if s.get('todays_offer') else ""
                context_str += f"  • {s['name']} (വാർഡ് {s['ward_number']}, ഫോൺ: {s['contact_phone']}{offer})\n"

        if recent_notices:
            context_str += "- പ്രധാന അറിയിപ്പുകൾ:\n"
            for n in recent_notices:
                alert = " [അടിയന്തരം!]" if n['is_emergency'] else ""
                context_str += f"  • {n['title']}{alert} (സ്ഥലം: {n.get('venue') or 'പഞ്ചായത്ത്'})\n"

        if emergency_services:
            context_str += "- അടിയന്തര നമ്പറുകൾ (Emergency Contacts):\n"
            for e in emergency_services:
                context_str += f"  • {e['name']} ({e['category']}): {e['phone_number']}\n"

        return context_str

    def _fallback_local_search(self, query):
        """
        Intelligent instant local keyword responder when no GEMINI_API_KEY is configured
        or during network offline mode (100% ₹0 guaranteed reliability).
        """
        q = query.lower()

        # 1. Emergency / Ambulance / Police
        if any(w in q for w in ['ആംബുലൻസ്', 'ambulance', 'പോലീസ്', 'police', 'ഫയർ', 'fire', 'അടിയന്തരം', 'hospital', 'ഡോക്ടർ']):
            contacts = DirectoryEntry.objects.filter(is_verified=True, is_emergency_service=True)[:4]
            if contacts.exists():
                res = "🚨 **പ്രധാന അടിയന്തര നമ്പറുകൾ:**\n"
                for c in contacts:
                    res += f"• **{c.name}**: {c.phone_number} ({c.address_or_stand})\n"
                res += "\nആപ്പിലെ 'ഡയറക്ടറി' ടാബിൽ കൂടുതൽ നമ്പറുകൾ ലഭ്യമാണ്."
                return res

        # 2. Open shops / Food / Items
        if any(w in q for w in ['കട', 'shop', 'തുറന്ന', 'ഭക്ഷണം', 'ഹോട്ടൽ', 'വാങ്ങാൻ', 'പലചരക്ക്']):
            shops = Shop.objects.filter(is_verified=True, is_open=True)[:4]
            if shops.exists():
                res = "🏪 **ഇപ്പോൾ തുറന്നിരിക്കുന്ന പ്രധാന കടകൾ:**\n"
                for s in shops:
                    offer = f" (ഓഫർ: {s.todays_offer})" if s.todays_offer else ""
                    res += f"• **{s.name}** - വാർഡ് {s.ward_number} | 📞 {s.contact_phone}{offer}\n"
                res += "\nകൂടുതൽ വിവരങ്ങൾക്ക് ആപ്പിലെ 'കടകൾ' വിഭാഗം പരിശോധിക്കുക."
                return res
            return "നിലവിൽ തുറന്നിരിക്കുന്ന കടകൾ ലഭ്യമല്ല. അൽപ്പസമയത്തിനകം വീണ്ടും നോക്കുക."

        # 3. Blood Donors
        if any(w in q for w in ['രക്തം', 'blood', 'ദാതാക്കൾ', 'donor']):
            donors = BloodDonor.objects.filter(is_available=True)[:4]
            if donors.exists():
                res = "🩸 **ലഭ്യമായ രക്തദാതാക്കൾ:**\n"
                for d in donors:
                    res += f"• {d.name} ({d.blood_group}) - വാർഡ് {d.ward_number} | 📞 {d.phone_number}\n"
                return res
            return "രക്തദാതാക്കളുടെ വിവരങ്ങൾ ലഭ്യമല്ല."

        # 4. Notices / Current Events
        if any(w in q for w in ['നോട്ടീസ്', 'അറിയിപ്പ്', 'കറണ്ട്', 'വെള്ളം', 'പരിപാടി', 'notice', 'event']):
            notices = EventNotice.objects.all().order_by('-is_emergency', '-created_at')[:3]
            if notices.exists():
                res = "📢 **പുതിയ അറിയിപ്പുകൾ:**\n"
                for n in notices:
                    alert = "⚠️ [അടിയന്തരം] " if n.is_emergency else ""
                    res += f"• **{alert}{n.title}**: {n.description[:100]}...\n"
                return res
            return "പുതിയ അറിയിപ്പുകൾ ഒന്നും ലഭ്യമല്ല."

        # Default friendly local assistant greeting
        return (
            "നമസ്കാരം! ഞാൻ 'എന്റെ നാട്' സ്മാർട്ട് അസിസ്റ്റന്റ് ആണ്. 🌴\n\n"
            "നിങ്ങൾക്ക് താഴെ പറയുന്ന കാര്യങ്ങൾ എന്നോട് ചോദിക്കാം:\n"
            "• 'ഇപ്പോൾ തുറന്നിരിക്കുന്ന കടകൾ ഏതൊക്കെയാണ്?'\n"
            "• 'ആംബുലൻസ് അല്ലെങ്കിൽ ഡോക്ടറുടെ നമ്പർ തരുമോ?'\n"
            "• 'പുതിയ നോട്ടീസുകൾ എന്തൊക്കെയാണ്?'\n"
            "• 'A+ രക്തദാതാക്കളുടെ ലിസ്റ്റ് ഉണ്ടോ?'"
        )

    def post(self, request):
        user_message = request.data.get('message', '').strip()
        if not user_message:
            return Response({'error': 'ദയവായി ഒരു സന്ദേശം ടൈപ്പ് ചെയ്യുക.'}, status=status.HTTP_400_BAD_REQUEST)

        gemini_api_key = os.environ.get('GEMINI_API_KEY')

        # If no external Gemini API key is configured, use fast intelligent local responder
        if not gemini_api_key:
            reply = self._fallback_local_search(user_message)
            return Response({
                'reply': reply,
                'source': 'local_engine',
                'assistant_name': 'നാട്ടു സഹായി'
            })

        # When GEMINI_API_KEY is present, query Google Gemini 1.5 Flash
        try:
            community_context = self._build_community_context()
            system_instruction = (
                "You are 'നാട്ടു സഹായി' (Nattu Sahayi), the friendly, knowledgeable local AI assistant "
                "for the village community app 'Ente Naadu' in Kerala, India. "
                "Always respond in natural, polite Malayalam language. "
                "Keep your answers concise, practical, helpful, and culturally respectful. "
                "Never disclose database secrets, passwords, or personal citizen credentials. "
                "If someone asks about local shops, notices, or emergency numbers, rely on this live village data:\n"
                f"{community_context}\n"
                "If you are not certain about a local service, guide them to contact the local Panchayat office."
            )

            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"System context:\n{system_instruction}\n\nUser Question:\n{user_message}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 600
                }
            }

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=12) as response:
                result_json = json.loads(response.read().decode('utf-8'))
                candidates = result_json.get('candidates', [])
                if candidates and 'content' in candidates[0]:
                    reply_text = candidates[0]['content']['parts'][0]['text']
                    return Response({
                        'reply': reply_text,
                        'source': 'gemini_flash',
                        'assistant_name': 'നാട്ടു സഹായി'
                    })

        except Exception as e:
            # Safe graceful degradation to local engine if network/API fails
            reply = self._fallback_local_search(user_message)
            return Response({
                'reply': reply,
                'source': 'fallback_local_engine',
                'assistant_name': 'നാട്ടു സഹായി'
            })

        reply = self._fallback_local_search(user_message)
        return Response({
            'reply': reply,
            'source': 'fallback_local_engine',
            'assistant_name': 'നാട്ടു സഹായി'
        })
