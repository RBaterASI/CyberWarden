# Cyber Warden - Artifact Signing setup checklist (nothing here has been done)

Legend: [YOU] only you can do it (account, identity, money, Windows settings) | [CLAUDE] I can do it after you approve | [GATE] stop and decide

## A. Before spending anything  [YOU]
- [ ] Azure subscription is pay-as-you-go (not free / trial / sponsored). Portal > Subscriptions > offer type.
- [ ] Azure billing account Account Type is "Individual"; legal name and sold-to address are exactly what is on the government ID you will use. Portal > Cost Management + Billing.
- [ ] You have a Microsoft Entra tenant, and you know its tenant ID and the subscription ID (these go into the local config, not Git).
- [ ] Phone with Microsoft Authenticator (latest), a US driver licence / passport / state ID, and a quiet well-lit place for the face check (third-party verifier AU10TIX).
- [ ] Read the Artifact Signing terms of use (certificate misuse leads to revocation / account suspension) and decide you accept your legal name appearing in every signed DLL's certificate.
- [GATE] Confirm the price on the Azure pricing page (Microsoft's SKU doc says Basic $9.99/month, 5,000 signatures, not prorated, billed from account creation).

## B. Azure resources  [YOU, portal]
- [ ] Register the `Microsoft.CodeSigning` resource provider on the subscription.
- [ ] Create the Artifact Signing account, Basic SKU, in a US region (note the region's endpoint, e.g. East US = https://eus.codesigning.azure.net).
- [ ] Assign yourself "Artifact Signing Identity Verifier", create an Individual > Public identity validation, finish the Verified ID steps. Wait for status Completed (days to weeks; renewal reminders start 60 days before expiry - put the expiry date in your calendar).
- [ ] Create a certificate profile of type **Public Trust** (NOT "Public Trust Test": its certificates are not trusted). Note the exact subject (CN=...).
- [ ] Assign yourself "Artifact Signing Certificate Profile Signer" on the account or profile.

## C. This PC  [YOU install, CLAUDE can verify]
- [ ] Azure CLI installed (`az` is not installed today) and `az login` done interactively with the same account; `az account show` shows the configured tenant and subscription.
- [ ] Artifact Signing client tools: `winget install -e --id Microsoft.Azure.ArtifactSigningClientTools`. Note the path of the x64 `Azure.CodeSigning.Dlib.dll`.
- [ ] Already present (checked read-only): SignTool 10.0.22621.5040 from SDK 22621, Microsoft-signed; .NET runtime 8.0.19. The 20348 SDK is not installed (it does not work with the dlib).
- [ ] Do NOT install any certificate, do NOT change Smart App Control, do NOT put a client secret in an environment variable (the script refuses to run if AZURE_CLIENT_SECRET / AZURE_PASSWORD is set).

## D. Local config  [CLAUDE after approval, you supply values]
- [ ] Create `%LOCALAPPDATA%\CyberWarden\ArtifactSigning\config.json` from `ArtifactSigning.config.example.json`: Endpoint, Account, Profile, TenantId, SubscriptionId, ExpectedCommonName (plain legal name, no CN=), DlibPath. Leave `"Mode": "Off"` for now.
- [ ] Compare the credential type names in `ExcludeCredentials` with `metadata.sample.json` shipped in the installed dlib; adjust the script if they differ.
- [ ] Confirm `Saved/` is Git-ignored (it is: .gitignore line 4), so state and log files never reach Git. Nothing in the repo contains a secret; the config holds identifiers only and lives outside the repo.

## E. Activation (each step needs your explicit go)  [GATE]
1. [ ] Review the proposed `BuildCpp.proposed.ps1`; I install it as `Tools/BuildCpp.ps1` (a normal reviewed change, not committed without your say-so).
2. [ ] `BuildCpp.ps1 -PreflightOnly` (no build, no signing, no Unreal): checks config, tools, Azure session.
3. [ ] Set `"Mode": "Required"`; one `BuildCpp.ps1` run. Expected: build, 1 signature, verification, state file written. If nothing recompiles the DLL, it signs the current one once (that uses 1 signature of 5,000).
4. [ ] `BuildCpp.ps1 -VerifyOnly` and a second plain run: expected "up to date", no Azure call, no new signature.
5. [ ] Inspect: `Get-AuthenticodeSignature` Status Valid, signer = your validated name, TimeStamperCertificate present, chain root = the Public Trust root (compare with ExpectedRoot default in the script; the root name is an assumption to confirm here).
6. [ ] ONE headless Unreal load of the signed DLL with Smart App Control still on (needs your approval). Read new Code Integrity events afterwards.
   - Loads: continue with the C2 plan (regenerate the data asset, final-approach validation).
   - Blocked again: stop, record events 3033/3077, delete the Artifact Signing account to stop billing, fall back to the VM option.

## F. Ongoing
- [ ] Identity validation expiry date on the calendar.
- [ ] `az login` after long idle periods (the script fails closed with a clear message).
- [ ] Monthly invoice about $10; signature use is one per changed DLL.
- [ ] If the subscription or tenant ever changes, all Artifact Signing resources must be recreated.

## G. Added after review v2
- [ ] Before step E1, run the offline suite `BuildCppSigning.Tests.ps1` once more against the exact script being installed (it uses mocks and a temp directory only; it never starts Unreal, Azure, az, dotnet, signtool or a build). Expected: `RESULT: N passed, 0 failed`.
- [ ] After the first real signature, copy the real chain root name and thumbprint (`Get-AuthenticodeSignature`, then the chain root) into `ExpectedRoot` / `ExpectedRootThumbprint`, and the real timestamp authority name into `ExpectedTimestampAuthority`, so the checks are pinned to what Microsoft actually issued.
- [ ] Confirm the dlib and SignTool are accepted by the script's "Microsoft-signed tool" check (preflight step E2). If the installed dlib is signed under another publisher name, that is a stop-and-ask, not something to switch off.
- [ ] Observe whether `signtool verify /pa` needs network access (revocation) when run offline; decide then whether offline builds are acceptable to block.
