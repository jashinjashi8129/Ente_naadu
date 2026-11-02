import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


def seed_initial_rating_criteria(apps, schema_editor):
    RatingCriterion = apps.get_model('shops', 'RatingCriterion')

    criteria_data = [
        # General Shop
        ('general', 'Product Quality', 'ഉൽപ്പന്ന ഗുണനിലവാരം', 'product_quality', 'Quality and freshness of items sold', 1),
        ('general', 'Price / Value', 'വില / മൂല്യം', 'price_value', 'Fair and competitive pricing', 2),
        ('general', 'Packing & Delivery', 'പാക്കിംഗും ഡെലിവറിയും', 'packing_delivery', 'Safe packaging and prompt delivery', 3),
        ('general', 'Customer Service', 'ഉപഭോക്തൃ സേവനം', 'customer_service', 'Politeness and responsiveness of staff', 4),

        # Beauty Parlour / Salon
        ('beauty_parlour', 'Service Quality', 'സേവന ഗുണനിലവാരം', 'service_quality', 'Quality of haircut, styling, or beauty treatments', 1),
        ('beauty_parlour', 'Staff Behaviour', 'ജീവനക്കാരുടെ പെരുമാറ്റം', 'staff_behaviour', 'Professionalism and courteousness', 2),
        ('beauty_parlour', 'Cleanliness & Hygiene', 'ശുചിത്വവും വൃത്തിയും', 'cleanliness_hygiene', 'Sanitization and clean salon environment', 3),
        ('beauty_parlour', 'Price / Value', 'വില / മൂല്യം', 'price_value', 'Value for money of services rendered', 4),
        ('beauty_parlour', 'Appointment Waiting Time', 'വെയ്റ്റിംഗ് സമയം', 'waiting_time', 'Punctuality and adherence to booked slots', 5),

        # Repair Shop
        ('repair', 'Repair Quality', 'റിപ്പയറിംഗ് ഗുണനിലവാരം', 'repair_quality', 'Effectiveness and durability of repair work', 1),
        ('repair', 'Service Time', 'സർവീസ് സമയം', 'service_time', 'Prompt turnaround and delivery on promised date', 2),
        ('repair', 'Price / Value', 'വില / മൂല്യം', 'price_value', 'Fair charges for spare parts and labor', 3),
        ('repair', 'Customer Support', 'കസ്റ്റമർ സപ്പോർട്ട്', 'customer_support', 'Clear explanation of issues and helpful updates', 4),

        # Restaurant / Hotel
        ('restaurant', 'Food Quality', 'ഭക്ഷണ ഗുണനിലവാരം', 'food_quality', 'Freshness and preparation of dishes', 1),
        ('restaurant', 'Taste', 'രുചി', 'taste', 'Flavor and culinary satisfaction', 2),
        ('restaurant', 'Cleanliness', 'ശുചിത്വം', 'cleanliness', 'Dining area and kitchen cleanliness', 3),
        ('restaurant', 'Customer Service', 'കസ്റ്റമർ സർവീസ്', 'customer_service', 'Attentive staff and fast serving', 4),
        ('restaurant', 'Price / Value', 'വില / മൂല്യം', 'price_value', 'Portion size and value for money', 5),

        # Other Service Businesses
        ('other_service', 'Service Quality', 'സേവന നിലവാരം', 'service_quality', 'Professional standards and execution', 1),
        ('other_service', 'Staff Behaviour', 'ജീവനക്കാരുടെ പെരുമാറ്റം', 'staff_behaviour', 'Helpful and respectful attitude', 2),
        ('other_service', 'Timeliness', 'കൃത്യനിഷ്ഠ', 'timeliness', 'Punctuality and respecting deadlines', 3),
        ('other_service', 'Price / Value', 'വില / മൂല്യം', 'price_value', 'Reasonable rates for services', 4),
        ('other_service', 'Customer Support', 'കസ്റ്റമർ സപ്പോർട്ട്', 'customer_support', 'Post-service communication and issue resolution', 5),

        # Medical Shop
        ('medical', 'Medicine Availability', 'മരുന്നുകളുടെ ലഭ്യത', 'medicine_availability', 'Availability of prescribed medications', 1),
        ('medical', 'Service Quality', 'സേവന നിലവാരം', 'service_quality', 'Pharmacist accuracy and guidance', 2),
        ('medical', 'Price / Value', 'വില / മൂല്യം', 'price_value', 'Accurate pricing and discounts', 3),
        ('medical', 'Customer Support', 'ഉപഭോക്തൃ സേവനം', 'customer_support', 'Helpful consultation and quick billing', 4),
    ]

    for bt, name, name_ml, slug, desc, order in criteria_data:
        RatingCriterion.objects.get_or_create(
            business_type=bt,
            slug=slug,
            category=None,
            defaults={
                'name': name,
                'name_ml': name_ml,
                'description': desc,
                'is_active': True,
                'order': order,
            }
        )


class Migration(migrations.Migration):

    dependencies = [
        ('shops', '0006_shopworkinghour_and_temporary_close'),
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RatingCriterion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('business_type', models.CharField(blank=True, choices=[('general', 'ജനറൽ സ്റ്റോർ (General Shop)'), ('beauty_parlour', 'ബ്യൂട്ടി പാർലർ / സലൂൺ (Beauty Parlour)'), ('medical', 'മെഡിക്കൽ ഷോപ്പ് (Medical Shop)'), ('repair', 'റിപ്പയർ / സർവീസ് (Repair Shop)'), ('restaurant', 'ഹോട്ടൽ / റസ്റ്റോറന്റ് (Restaurant)'), ('other_service', 'മറ്റു സേവനങ്ങൾ (Other Services)')], help_text='Default criteria applied across this business type', max_length=30, null=True, verbose_name='സ്ഥാപന തരം (Business Type)')),
                ('name', models.CharField(max_length=100, verbose_name='മാനദണ്ഡം (Criterion Name, e.g. Product Quality)')),
                ('name_ml', models.CharField(blank=True, max_length=150, verbose_name='മലയാളം പേര് (Malayalam Name)')),
                ('slug', models.SlugField(max_length=100, verbose_name='സ്ലഗ് (Identifier Slug)')),
                ('description', models.CharField(blank=True, max_length=255, verbose_name='വിവരണം (Description)')),
                ('is_active', models.BooleanField(default=True, verbose_name='സജീവമാണോ (Is Active)')),
                ('order', models.PositiveIntegerField(default=0, verbose_name='ക്രമം (Display Order)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(blank=True, help_text='Leave blank to apply to all categories of the selected business type', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='rating_criteria', to='shops.shopcategory', verbose_name='ഷോപ്പ് വിഭാഗം (Specific Category)')),
            ],
            options={
                'verbose_name': 'റേറ്റിംഗ് മാനദണ്ഡം (Rating Criterion)',
                'verbose_name_plural': 'റേറ്റിംഗ് മാനദണ്ഡങ്ങൾ (Rating Criteria)',
                'ordering': ['order', 'name'],
            },
        ),
        migrations.AddField(
            model_name='review',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviews', to='orders.order', verbose_name='ഓർഡർ (Order)'),
        ),
        migrations.AddField(
            model_name='review',
            name='booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviews', to='orders.booking', verbose_name='ബുക്കിംഗ് (Booking)'),
        ),
        migrations.AddField(
            model_name='review',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='review',
            name='comment',
            field=models.TextField(blank=True, verbose_name='അഭിപ്രായം (Review)'),
        ),
        migrations.AlterField(
            model_name='review',
            name='rating',
            field=models.PositiveSmallIntegerField(choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')], validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='റേറ്റിംഗ്'),
        ),
        migrations.CreateModel(
            name='ReviewCriterionRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criterion_name', models.CharField(max_length=100, verbose_name='മാനദണ്ഡം (Criterion Name Snapshot)')),
                ('criterion_name_ml', models.CharField(blank=True, max_length=150, verbose_name='മലയാളം പേര് (Malayalam Snapshot)')),
                ('criterion_slug', models.CharField(db_index=True, max_length=100, verbose_name='സ്ലഗ് (Snapshot Slug)')),
                ('rating', models.PositiveSmallIntegerField(choices=[(1, '1 Star'), (2, '2 Stars'), (3, '3 Stars'), (4, '4 Stars'), (5, '5 Stars')], validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(5)], verbose_name='റേറ്റിംഗ് (1-5 Stars)')),
                ('feedback', models.TextField(blank=True, verbose_name='പ്രത്യേക അഭിപ്രായം (Optional Feedback)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('criterion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='criterion_scores', to='shops.ratingcriterion', verbose_name='മാനദണ്ഡം (Criterion)')),
                ('review', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='criterion_ratings', to='shops.review', verbose_name='റിവ്യൂ (Review)')),
            ],
            options={
                'verbose_name': 'മാനദണ്ഡ റേറ്റിംഗ് (Review Criterion Rating)',
                'verbose_name_plural': 'മാനദണ്ഡ റേറ്റിംഗുകൾ (Review Criterion Ratings)',
                'ordering': ['created_at'],
                'unique_together': {('review', 'criterion_slug')},
            },
        ),
        migrations.RunPython(seed_initial_rating_criteria, reverse_code=migrations.RunPython.noop),
    ]
