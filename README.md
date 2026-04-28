# Micro-CT Ring Removal GUI

A desktop GUI for batch ring-removal and reconstruction workflows for Micro-CT data.

## Main user workflow

1. Install **Conda/Miniforge/Anaconda** and configure Conda channels.
2. Install the **CERA Python wheel** into the **base** environment (recommended).
3. Install the GUI environment by double-clicking **`install_ring_removal_env.bat`**.
4. Start the program by double-clicking **`GUI_RR.bat`**.
5. To update the code later, use `git pull` inside the `ring_removal` folder.

---

## 1. Prerequisites

Before installing this program, make sure you have:

- **Windows**
- **Git** installed
- **Conda** installed (Miniforge is recommended)
- **CERA** installed on the machine
- Access to the correct **CERA Python wheel (`cerapy`)** from your CERA installation

### Recommended Conda distribution

A lightweight and reliable option is **Miniforge**.

After installation, open **Anaconda Prompt**, **Miniforge Prompt**, or a normal terminal where `conda` works.

---

## 2. Configure Conda channels

This project should use **conda-forge** as the main channel.

Run these commands:

```bash
conda config --remove-key channels
conda config --add channels conda-forge
conda config --add channels defaults
conda config --set channel_priority strict
conda config --get channels
```

Expected order:

```text
channels:
  - conda-forge
  - defaults
```

If your network blocks Conda package servers, environment creation may fail with connection errors. In that case, first check your internet connection, firewall, VPN, proxy settings, or ask your local IT support whether access to Conda repositories is blocked.

---

## 3. Install the CERA Python wheel

### Important

The CERA Python binding must be installed in the Python environment that will be used to run CERA from the GUI.

**Recommended setup:** install it into the **base** Conda environment.

This is the safest default because the GUI can then use the base Python executable for CERA-related commands.

### Check Python version required by the wheel

Look at the wheel filename. Example:

```text
cerapy-7.1.0.20241025.2078853661.0-cp313-cp313-win_amd64.whl
```

Here, `cp313` means the wheel requires **Python 3.13**.

So the environment where you install this wheel must use the matching Python version.

### Recommended installation steps

Activate base:

```bash
conda activate base
```

Make sure base uses the correct Python version for your wheel. For a `cp313` wheel:

```bash
conda install python=3.13
```

Install NumPy first:

```bash
python -m pip install numpy
```

Then install the CERA wheel, for example:

```bash
python -m pip install "C:\Program Files (x86)\CERA-7.1.0\CERA-7.1.0\CERA\language_bindings\python\dist\cerapy-7.1.0.20241025.2078853661.0-cp313-cp313-win_amd64.whl"
```

### Test the installation

Run:

```bash
python -c "import cerapy; print('cerapy OK')"
```

If everything is correct, you should see:

```text
cerapy OK
```

### Common problem: NumPy missing

If you see an error like:

```text
ModuleNotFoundError: No module named 'numpy'
```

then NumPy is missing in the environment where `cerapy` was installed.

Fix it with:

```bash
conda activate base
python -m pip install numpy
```

and test again:

```bash
python -c "import cerapy; print('cerapy OK')"
```

### Using another environment instead of base

This is possible, but then:

- the wheel must be installed in that environment,
- Python version must match the wheel,
- and the GUI/configuration must point to that Python executable.

For most users, **base is recommended**.

---

## 4. Download the code from GitHub

Clone the repository:

```bash
git clone https://github.com/mickalp/ring_removal.git
cd ring_removal
```

If you already downloaded the project earlier, you do not need to clone again.

---

## 5. Install the GUI environment

Inside the project folder, run:

- double-click **`install_ring_removal_env.bat`**

or from terminal:

```bash
install_ring_removal_env.bat
```

This script creates/updates the Conda environment required by the GUI.

If installation fails, first verify:

- Conda is installed correctly
- Conda channels are configured as described above
- Internet connection is available
- Conda repositories are not blocked by firewall/proxy

---

## 6. Start the program

To launch the GUI:

- double-click **`GUI_RR.bat`**

This should start the Ring Removal GUI.

---

## 7. Updating the code later

To update the local copy of the project to the latest GitHub version, open terminal in the project folder and run:

```bash
cd ring_removal
git pull
```

### Recommended after update

After pulling new code, update the environment again just in case dependencies changed:

- double-click **`install_ring_removal_env.bat`**

or run:

```bash
install_ring_removal_env.bat
```

Then start the GUI again with:

- **`GUI_RR.bat`**

---

## 8. Quick installation summary

For advanced users, the full installation is:

```bash
conda config --remove-key channels
conda config --add channels conda-forge
conda config --add channels defaults
conda config --set channel_priority strict
conda activate base
conda install python=3.13
python -m pip install numpy
python -m pip install "C:\Program Files (x86)\CERA-7.1.0\CERA-7.1.0\CERA\language_bindings\python\dist\cerapy-7.1.0.20241025.2078853661.0-cp313-cp313-win_amd64.whl"
git clone https://github.com/mickalp/ring_removal.git
cd ring_removal
install_ring_removal_env.bat
```

Then launch with:

```text
GUI_RR.bat
```

---

## 9. Troubleshooting

### CondaHTTPError / connection failed

Example:

```text
CondaHTTPError: HTTP 000 CONNECTION FAILED
```

This usually means one of these:

- no internet connection,
- firewall/proxy/VPN is blocking Conda,
- company/institute network blocks access to Conda repositories,
- temporary server/network issue.

Try again first. If the problem remains, test on another network or contact local IT support.

### `cerapy` import fails

Check all of the following:

- wheel is installed in the correct environment,
- Python version matches the wheel (`cp313` → Python 3.13),
- NumPy is installed in the same environment,
- CERA itself is installed correctly on the machine.

### `git pull` does not work

Make sure you are inside the repository folder:

```bash
cd ring_removal
```

Then run:

```bash
git pull
```

If you made your own local code changes and Git refuses to pull, commit your changes first or make a backup copy of the folder.

---

## 10. Notes

- Installing the CERA wheel in **base** is the recommended default.
- The wheel must match the Python version exactly.
- After updating the repository, it is good practice to rerun **`install_ring_removal_env.bat`**.

---

## 11. Launch checklist

Before starting the GUI, make sure:

- Conda is installed
- `conda-forge` is configured in Conda channels
- CERA is installed
- `cerapy` wheel is installed successfully
- `import cerapy` works
- GUI environment was created with `install_ring_removal_env.bat`

After that, launch with:

```text
GUI_RR.bat
```
