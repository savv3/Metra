# Messages and newsletters

## Email settings

An admin decides how email is sent under **Settings > Email**, which is also a
step of the setup wizard. Choose **SMTP** to send through the association's own
mail account: enter the **Mail server**, **Port**, **Encryption**, **User name**
and **Password** your email provider gives you. An add-on can offer a sending
service instead. Set the **From address** members see, and a **Reply-To
address** if replies should go somewhere else. All email from Metra goes this
way, including login codes and invitations. **Send test email** checks that it
works. A saved password is never shown again: leave the field empty to keep it.
A field that is greyed out is set on the server and cannot be changed in the
app.

### Mailgun

The **Mailgun** add-on sends email through Mailgun instead. Enter the
**Sending domain**, **API key** and **Region** under **Settings > Add-ons >
Mailgun**, then choose **Mailgun** under **Settings > Email**. With the
**Webhook signing key** filled in and the webhook added at Mailgun (see the
installation guide), each message's status shows whether it was delivered.
When an email bounces, the message is marked failed and the person's page
shows **Bounced** next to the address, with Mailgun's reason. Check the
address with the person and correct it; a new address clears the mark. An
email the recipient marked as spam is noted on the message.

## Writing to many households

**Send-outs > New message** writes one message to everyone, to units with a
tag or of a type, or to the units in the list you have filtered (**Send a
message to these units** under the unit list). Choose whether it goes to all
contacts of each unit or only the main contact, and how. The usual choice is
**Each person's preferred channel**: those who prefer email get an email and
those who prefer SMS get an SMS, or the other one when they have no address
for it (or it fails). There are no letters for these messages, so those who
prefer post get an SMS, or else an email. The preferred channel is set on each
person's page. Under **Other options** you can instead choose, whatever people
prefer:

- **SMS only** or **Email only**,
- **SMS, or email for those without a phone**, or
- **Both SMS and email**.

With the preferred channel, write both the SMS text and the email subject,
since people may get either. The form shows only the texts the chosen way
needs. Placeholders such as
`{first_name}` and `{unit}` are filled in for each person, and a counter shows
how many SMS the text takes. Before anything is sent, a check page shows how
many get an SMS and an email, and who cannot be reached, so someone can call
them.

## Urgent alerts

**Urgent alert** (the red button) is for disruptions such as a water leak. It
goes by SMS and email to every contact of every active unit at once, whatever
they prefer, and can also be shown as a notice on the public page. The send-out page shows each
person's delivery status as it goes.

## One household

On a unit's page, **Send message** under **Messages** writes to that unit's
contacts, by default on each one's preferred channel. The same section lists
everything they have been sent: links, reminders, invoices and messages.

## Attachments

Messages and newsletters can carry files, such as the agenda for the annual
meeting: PDF, images and office documents. Email recipients get them
attached; SMS recipients get a short link at the end of the SMS.

## Newsletters

Newsletters go by email only, and only to people who have said yes. A
person's answer is recorded on their page, with when and how it was given,
and members can change it on their own page. **Send-outs > New newsletter**
writes and sends one. Every newsletter ends with a link to unsubscribe.

Service messages and alerts are not newsletters: they are about your own
service, so they reach everyone.
