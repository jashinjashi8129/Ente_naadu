from django.contrib import admin
from .models import DirectoryEntry, BloodDonor, ClassifiedAd

@admin.register(DirectoryEntry)
class DirectoryEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'phone_number', 'address_or_stand', 'ward_number', 'is_emergency_service', 'is_verified', 'submitted_by', 'created_at')
    list_filter = ('is_verified', 'category', 'is_emergency_service', 'ward_number')
    search_fields = ('name', 'phone_number', 'address_or_stand', 'submitted_by__full_name', 'submitted_by__phone_number')
    actions = ['approve_entries']

    @admin.action(description="തിരഞ്ഞെടുത്ത സേവനങ്ങൾക്ക് അംഗീകാരം നൽകുക (Approve)")
    def approve_entries(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f"{count} സേവനങ്ങൾക്ക് വിജയകരമായി അംഗീകാരം നൽകി.")

@admin.register(BloodDonor)
class BloodDonorAdmin(admin.ModelAdmin):
    list_display = ('name', 'blood_group', 'phone_number', 'ward_number', 'is_available', 'last_donated_date')
    list_filter = ('blood_group', 'is_available', 'ward_number')
    search_fields = ('name', 'phone_number')

@admin.register(ClassifiedAd)
class ClassifiedAdAdmin(admin.ModelAdmin):
    list_display = ('title', 'ad_type', 'author', 'contact_phone', 'price_or_salary', 'is_approved', 'created_at')
    list_filter = ('ad_type', 'is_approved', 'created_at')
    search_fields = ('title', 'description', 'contact_phone', 'author__full_name')
