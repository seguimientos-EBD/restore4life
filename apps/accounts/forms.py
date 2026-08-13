from django import forms


class EmailForm(forms.Form):
    email = forms.EmailField(
        label='Email address',
        widget=forms.EmailInput(attrs={'placeholder': 'Email address'}),
    )